"""Local synthetic integrity controls for the G5 data binder, not native acceptance."""
from __future__ import annotations

import hashlib
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

TOOL = Path(__file__).resolve().parents[1] / "tools/sota-convergence/merge_fragments.py"
SPEC = importlib.util.spec_from_file_location("g5_merge_fragments", TOOL)
merge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(merge)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MergeFragmentTests(unittest.TestCase):
    @staticmethod
    def compact_row(label="WATCH", pin="a" * 40, role=None):
        result = {"repository_or_entry": "example/project", "slot": "workers", "qualification": {} if role is None else {"role": role},
                  "disposition": label, "evidence_class": "SOURCE-REVIEW", "pin": {"kind": "commit", "version_or_commit": pin,
                  "repository_or_source": "example/project", "subject": "implementation"},
                  "primary_sources": [{"locator": "example/project@" + pin + ":README.md:1",
                                       "pin": {"kind": "commit", "version_or_commit": pin, "repository_or_source": "example/project", "subject": "implementation"},
                                       "subject": "Pinned vendor documentation"}],
                  "archive_member": "captures/source.json", "capture_sha256": "c" * 64,
                  "owner_lane": "source-lane", "refresh_date": "2026-10-08"}
        if label == "PENDING":
            result["pending"] = {"provisional_disposition": "WATCH", "measurement": "Verify source", "owner": "source-lane"}
        return result

    def witnessed_row(self, evidence="SOURCE-REVIEW", label="WATCH"):
        row = self.compact_row(label)
        row["evidence_class"] = evidence
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        repository = Path(directory.name) / "source.git"
        environment = {"PATH": os.defpath, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                       "GIT_AUTHOR_NAME": "Synthetic control", "GIT_AUTHOR_EMAIL": "control@example.invalid",
                       "GIT_COMMITTER_NAME": "Synthetic control", "GIT_COMMITTER_EMAIL": "control@example.invalid",
                       "GIT_AUTHOR_DATE": "2026-10-08T00:00:00Z", "GIT_COMMITTER_DATE": "2026-10-08T00:00:00Z"}
        subprocess.run(["git", "init", "--quiet", "--bare", str(repository)], check=True, env=environment)
        def git(*args, raw=None):
            return subprocess.run(["git", "--git-dir", str(repository), *args], input=raw,
                                  capture_output=True, check=True, env=environment).stdout
        primary_body = b"# Synthetic vendor source\nA local witness control; no candidate execution.\n"
        blob_id = git("hash-object", "-w", "--stdin", raw=primary_body).decode().strip()
        tree_id = git("mktree", raw=f"100644 blob {blob_id}\tREADME.md\n".encode()).decode().strip()
        commit_id = git("commit-tree", tree_id, raw=b"Synthetic source custody\n").decode().strip()
        row["pin"]["version_or_commit"] = commit_id
        primary = row["primary_sources"][0]
        primary["pin"]["version_or_commit"] = commit_id
        primary["locator"] = f"example/project@{commit_id}:README.md:1"
        primary["archive_member"] = "captures/README.md"
        primary["capture_sha256"] = hashlib.sha256(primary_body).hexdigest()
        captures = {primary["archive_member"]: primary_body}
        objects = []
        for kind, object_id in (("commit", commit_id), ("tree", tree_id)):
            member = f"captures/{kind}.git-object"
            data = git("cat-file", kind, object_id)
            captures[member] = data
            objects.append({"object_type": kind, "object_id": object_id, "archive_member": member,
                            "sha256": hashlib.sha256(data).hexdigest()})
        proof = {"schema_version": 1, "repository": "example/project", "commit": commit_id,
                 "path": "README.md", "blob_id": blob_id, "objects": objects,
                 "body": {"archive_member": primary["archive_member"], "sha256": primary["capture_sha256"]}}
        proof_raw = json.dumps(proof, sort_keys=True).encode()
        captures["captures/pin-witness.json"] = proof_raw
        primary["pin_witness"] = {"archive_member": "captures/pin-witness.json", "sha256": hashlib.sha256(proof_raw).hexdigest(), "pointer": ""}
        body = {"source": "Pinned vendor source; local synthetic witness control"}
        row["source_pointer"] = "/source"
        if evidence in merge.compact.RECORDED:
            body["receipt"] = {
                "repository_or_entry": row["repository_or_entry"], "slot": row["slot"],
                "qualification": row["qualification"], "pin": row["pin"],
                "evidence_class": evidence, "executed": True, "status": "PASS", "exit_code": 0,
                "command": "vendor-test --fixture synthetic", "evidence_scope": "synthetic recorded receipt control",
            }
            row["acceptance_witness"] = {"archive_member": row["archive_member"], "pointer": "/receipt"}
        raw = json.dumps(body, sort_keys=True).encode()
        sha = hashlib.sha256(raw).hexdigest()
        row["capture_sha256"] = sha
        if "acceptance_witness" in row:
            row["acceptance_witness"]["sha256"] = sha
        captures[row["archive_member"]] = raw
        return row, captures

    def merge_witness_rows(self, rows, captures):
        captures = dict(captures)
        inputs = []
        for i, row in enumerate(rows):
            member = f"inputs/{i}.json"
            raw = json.dumps([row], sort_keys=True).encode()
            captures[member] = raw
            inputs.append(([row], member, hashlib.sha256(raw).hexdigest(), f"fragment-{i}"))
        result, receipt = merge.merge_compact_groups(inputs, captures=captures)
        index = {member: {"sha256": hashlib.sha256(raw).hexdigest()} for member, raw in captures.items()}
        return result[0], receipt, index

    def test_pending_all_unknown_keeps_default_guard_and_start_residue(self):
        row, captures = self.witnessed_row("UNKNOWN", "PENDING")
        result, _, index = self.merge_witness_rows([row], captures)
        self.assertEqual(result["evidence_class"], "UNKNOWN")
        for profile in (None, "start-closure/1"):
            with self.subTest(profile=profile):
                checked = copy.deepcopy(result)
                if profile is None:
                    for source in checked["primary_sources"]:
                        source.pop("pin_witness", None)
                blockers = merge.compact.validate_row(checked, index, profile)
                if profile is None:
                    self.assertIn("unknown-evidence-class", blockers)
                else:
                    self.assertNotIn("unknown-evidence-class", blockers)
                    self.assertEqual(checked["closure"]["residue"][0]["reason_code"], "evidence-class-unassessed")
                    self.assertEqual(checked["closure"]["residue"][0]["bucket"], "G5-F4")
        action = copy.deepcopy(result)
        action["disposition"] = "TRIAL"
        action.pop("pending")
        self.assertIn("unknown-evidence-class", merge.compact.validate_row(action, index, "start-closure/1"))
        self.assertNotIn("closure", action)

    def test_pending_witnessed_recorded_and_source_review_caps_execution(self):
        for evidence in sorted(merge.compact.RECORDED):
            with self.subTest(evidence=evidence):
                recorded, captures = self.witnessed_row(evidence, "TRIAL")
                reviewed = copy.deepcopy(recorded)
                reviewed["evidence_class"] = "SOURCE-REVIEW"
                reviewed.pop("acceptance_witness")
                result, _, _ = self.merge_witness_rows([recorded, reviewed], captures)
                self.assertEqual(result["evidence_class"], "SOURCE-REVIEW")
                self.assertNotIn("acceptance_witness", result)

    def test_pending_witnessed_source_review_is_not_erased_by_unknown(self):
        reviewed, captures = self.witnessed_row()
        unknown = copy.deepcopy(reviewed)
        unknown["evidence_class"] = "UNKNOWN"
        result, _, _ = self.merge_witness_rows([unknown, reviewed], captures)
        self.assertEqual(result["evidence_class"], "SOURCE-REVIEW")

    def test_pending_unwitnessed_source_review_and_unknown_gives_unknown(self):
        reviewed = self.compact_row()
        unknown = copy.deepcopy(reviewed)
        unknown["evidence_class"] = "UNKNOWN"
        result, _, _ = self.merge_witness_rows([reviewed, unknown], {})
        self.assertEqual(result["evidence_class"], "UNKNOWN")

    def test_profile_residue_cannot_establish_candidate_class_witness(self):
        reviewed, captures = self.witnessed_row()
        raw = b"Retained text cannot satisfy the declared JSON source selector.\n"
        reviewed["capture_sha256"] = hashlib.sha256(raw).hexdigest()
        captures[reviewed["archive_member"]] = raw
        index = {member: {"sha256": hashlib.sha256(data).hexdigest()} for member, data in captures.items()}
        for profile in (None, "start-closure/1"):
            with self.subTest(profile=profile):
                row = copy.deepcopy(reviewed)
                blockers = []
                cache = {}
                try:
                    self.assertEqual(merge.compact.validate_evidence_witness(row, index, captures, cache, blockers, profile), "UNKNOWN")
                finally:
                    if "_primary_git_cache" in cache:
                        cache["_primary_git_cache"][0].cleanup()
                if profile is None:
                    self.assertEqual([item["code"] for item in blockers], ["unsupported-json-pointer-capture"])
                else:
                    self.assertFalse(blockers)
                    self.assertEqual(row["closure"]["residue"][0]["reason_code"], "unsupported-json-pointer-capture")

    def test_pending_uses_strongest_witnessed_class_without_upgrading_documentary(self):
        documentary, captures = self.witnessed_row("DOCUMENTARY")
        unknown = copy.deepcopy(documentary)
        unknown["evidence_class"] = "UNKNOWN"
        result, _, _ = self.merge_witness_rows([documentary, unknown], captures)
        self.assertEqual(result["evidence_class"], "DOCUMENTARY")

        reviewed = copy.deepcopy(documentary)
        reviewed["evidence_class"] = "SOURCE-REVIEW"
        reviewed["source_pointer"] = "/missing"
        result, _, _ = self.merge_witness_rows([reviewed, documentary], captures)
        self.assertEqual(result["evidence_class"], "DOCUMENTARY")

    def test_unknown_claim_residue_uses_final_disposition_and_cannot_be_forged(self):
        claim, captures = self.witnessed_row("SOURCE-REVIEW", "TRIAL")
        claim["source_pointer"] = "/missing"
        claim_raw = json.dumps([claim], sort_keys=True).encode()
        member = "captures/original-claim.json"
        captures[member] = claim_raw
        ref = {"archive_member": member, "sha256": hashlib.sha256(claim_raw).hexdigest(), "pointer": "/0"}
        index = {name: {"sha256": hashlib.sha256(data).hexdigest()} for name, data in captures.items()}
        row = copy.deepcopy(claim)
        row["disposition"], row["evidence_class"] = "PENDING", "UNKNOWN"
        row["pending"] = {"provisional_disposition": "WATCH", "measurement": "Assess original unsupported claim", "owner": "synthetic-controls"}
        row["evidence_class_witness"] = ref
        row["source_refs"] = [ref]
        row["closure"] = {"unknown_evidence_reasons": ["unresolved-capture-pointer"]}
        # Only CC's enumerated unsupported-claim classes can replace F4.
        with self.assertRaisesRegex(merge.compact.CompactError, "unsupported UNKNOWN evidence reason"):
            merge.compact.validate_row(row, index, "start-closure/1")
        raw = b"Opaque retained text, unavailable as the declared JSON selector.\n"
        claim["capture_sha256"] = hashlib.sha256(raw).hexdigest()
        captures[claim["archive_member"]] = raw
        captures[member] = json.dumps([claim], sort_keys=True).encode()
        ref["sha256"] = hashlib.sha256(captures[member]).hexdigest()
        row["capture_sha256"] = claim["capture_sha256"]
        row["closure"] = {"unknown_evidence_reasons": ["unsupported-json-pointer-capture"]}
        index = {name: {"sha256": hashlib.sha256(data).hexdigest()} for name, data in captures.items()}
        blockers = []
        self.assertNotIn("unknown-evidence-class", merge.compact.validate_row(row, index, "start-closure/1"))
        cache = {}
        self.assertEqual(merge.compact.validate_evidence_witness(row, index, captures, cache, blockers, "start-closure/1"), "UNKNOWN")
        self.assertFalse(blockers)
        self.assertEqual([item["reason_code"] for item in row["closure"]["residue"]], ["unsupported-json-pointer-capture"])
        action = copy.deepcopy(row)
        action["disposition"] = "TRIAL"
        action.pop("pending")
        action["closure"].pop("residue")
        self.assertIn("unknown-evidence-class", merge.compact.validate_row(action, index, "start-closure/1"))
        blockers = []
        merge.compact.validate_evidence_witness(action, index, captures, {}, blockers, "start-closure/1")
        self.assertEqual([item["code"] for item in blockers], ["unsupported-json-pointer-capture"])
        forged = copy.deepcopy(row)
        forged["closure"]["unknown_evidence_reasons"] = ["original-source-entry-identity-unbound"]
        with self.assertRaisesRegex(merge.compact.CompactError, "reasons differ from the original native"):
            merge.compact.validate_evidence_witness(forged, index, captures, {}, [], "start-closure/1")

    def test_pending_invalid_recorded_receipt_cannot_support_source_review(self):
        recorded, captures = self.witnessed_row("RECORDED-UPSTREAM-TEST", "TRIAL")
        body = json.loads(captures[recorded["archive_member"]])
        body["receipt"]["executed"] = False
        raw = json.dumps(body, sort_keys=True).encode()
        sha = hashlib.sha256(raw).hexdigest()
        captures[recorded["archive_member"]] = raw
        recorded["capture_sha256"] = recorded["acceptance_witness"]["sha256"] = sha
        unknown = copy.deepcopy(recorded)
        unknown["evidence_class"] = "UNKNOWN"
        unknown.pop("acceptance_witness")
        result, _, _ = self.merge_witness_rows([recorded, unknown], captures)
        self.assertEqual(result["evidence_class"], "UNKNOWN")

    def test_native_reconciliation_preserves_final_actions_and_requires_fresh_assessment(self):
        original, captures = self.witnessed_row("UNKNOWN", "PENDING")
        raw = json.dumps([original], sort_keys=True).encode()
        member = "inputs/original.json"
        captures[member] = raw
        ref = {"archive_member": member, "sha256": hashlib.sha256(raw).hexdigest(), "pointer": "/0"}
        inputs = [([original], member, ref["sha256"], "original")]
        final = copy.deepcopy(original)
        final["disposition"], final["evidence_class"] = "TRIAL", "SOURCE-REVIEW"
        final.pop("pending")
        final["source_refs"] = [ref]
        rows, receipt = merge.reconcile_compact_classes([final], inputs, captures)
        self.assertEqual(rows[0]["disposition"], "TRIAL")
        self.assertEqual(rows[0]["evidence_class"], "UNKNOWN")
        self.assertEqual(rows[0]["evidence_class_witness"], ref)
        index = {name: {"sha256": hashlib.sha256(data).hexdigest()} for name, data in captures.items()}
        self.assertIn("unknown-evidence-class", merge.compact.validate_row(rows[0], index, "start-closure/1"))
        key = merge.compact.decision_key(final)
        rows, receipt = merge.reconcile_compact_classes([final], inputs, captures, assessed_keys=[key])
        self.assertEqual(rows[0]["evidence_class"], "SOURCE-REVIEW")
        self.assertEqual(receipt["fresh_assessments"], 1)
        self.assertEqual(rows[0]["source_refs"], final["source_refs"])
        final["primary_sources"][0].pop("pin_witness")
        with self.assertRaisesRegex(merge.FragmentError, "assessment has no retained witness"):
            merge.reconcile_compact_classes([final], inputs, captures, assessed_keys=[key])

    def test_native_pin_witness_rejects_tampered_objects_and_line_bounds(self):
        row, captures = self.witnessed_row()
        source = row["primary_sources"][0]
        index = {name: {"sha256": hashlib.sha256(data).hexdigest()} for name, data in captures.items()}
        cache = {}
        try:
            self.assertTrue(merge.compact.validate_primary_pin_witness(source, index, captures, cache))
            wrong = copy.deepcopy(source)
            wrong["locator"] = wrong["locator"].rsplit(":", 1)[0] + ":99"
            with self.assertRaisesRegex(merge.compact.CompactError, "line selector lies outside"):
                merge.compact.validate_primary_pin_witness(wrong, index, captures, cache)
        finally:
            cache["_primary_git_cache"][0].cleanup()

    def test_native_pin_witness_rejects_reforged_object_hashes(self):
        row, captures = self.witnessed_row()
        source = row["primary_sources"][0]
        proof_ref = source["pin_witness"]
        proof = json.loads(captures[proof_ref["archive_member"]])
        object_member = proof["objects"][0]["archive_member"]
        altered = captures[object_member] + b"tampered\n"
        captures[object_member] = altered
        proof["objects"][0]["sha256"] = hashlib.sha256(altered).hexdigest()
        proof_raw = json.dumps(proof, sort_keys=True).encode()
        captures[proof_ref["archive_member"]] = proof_raw
        proof_ref["sha256"] = hashlib.sha256(proof_raw).hexdigest()
        index = {name: {"sha256": hashlib.sha256(data).hexdigest()} for name, data in captures.items()}
        cache = {}
        try:
            with self.assertRaisesRegex(merge.compact.CompactError, "object ID differs"):
                merge.compact.validate_primary_pin_witness(source, index, captures, cache)
        finally:
            cache["_primary_git_cache"][0].cleanup()

    def test_native_tree_pin_witness_verifies_metadata_and_never_release_text(self):
        row, captures = self.witnessed_row()
        primary = row["primary_sources"][0]
        old = json.loads(captures[primary["pin_witness"]["archive_member"]])
        listing = b"100644 blob " + old["blob_id"].encode() + b"\tREADME.md\0"
        listing_member = "captures/tree-listing.z"
        captures[listing_member] = listing
        proof = {"schema_version": 1, "repository": "example/project", "declared_pin": old["commit"],
                 "declared_pin_kind": "commit", "non_file_kind": "tree", "commit": old["commit"],
                 "object_id": old["commit"], "root_tree_id": old["objects"][1]["object_id"],
                 "objects": old["objects"], "tag_object_type": None, "release_note_text_attested": False,
                 "boundary": "Git metadata only",
                 "native_recursive_tree_listing": {"archive_member": listing_member, "sha256": hashlib.sha256(listing).hexdigest()}}
        raw = json.dumps(proof, sort_keys=True).encode()
        member = "captures/tree-witness.json"
        captures[member] = raw
        primary.update(locator=f"https://github.com/example/project/tree/{old['commit']}",
                       archive_member=member, capture_sha256=hashlib.sha256(raw).hexdigest(), pointer="",
                       pin_witness={"archive_member": member, "sha256": hashlib.sha256(raw).hexdigest(), "pointer": ""})
        index = {name: {"sha256": hashlib.sha256(data).hexdigest()} for name, data in captures.items()}
        self.assertTrue(merge.compact.validate_primary_pin_witness(primary, index, captures, {}))
        proof["commit"] = "0" * 40
        raw = json.dumps(proof, sort_keys=True).encode()
        captures[member] = raw
        primary["capture_sha256"] = primary["pin_witness"]["sha256"] = hashlib.sha256(raw).hexdigest()
        index[member]["sha256"] = primary["capture_sha256"]
        with self.assertRaisesRegex(merge.compact.CompactError, "tag/commit mapping differs"):
            merge.compact.validate_primary_pin_witness(primary, index, captures, {})

    def test_real_gdelt_fragment_keeps_unknown(self):
        fixture = json.loads((Path(__file__).parent / "fixtures/g5-merge-gdelt.json").read_text())
        row = fixture["row"]
        canonical = json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), fixture["row_sha256"])
        self.assertEqual(fixture["source_pointer"], "/14")
        self.assertEqual(row["repository_or_entry"], "alex9smith/gdelt-doc-api")
        rows, _ = merge.merge_compact_groups([
            ([row], fixture["source_member"], fixture["source_sha256"], "g5-fields-b/us-equities/market-data-reference/public-safe"),
        ])
        self.assertEqual(rows[0]["evidence_class"], "UNKNOWN")

    def test_unpinned_source_claim_keeps_pin_residue_without_an_f4_event(self):
        original, captures = self.witnessed_row("SOURCE-REVIEW", "PENDING")
        original["pin"] = None
        original["primary_sources"][0]["pin"] = None
        original["primary_sources"][0].pop("pin_witness")
        raw = json.dumps([original], sort_keys=True).encode()
        member = "inputs/unpinned-original.json"
        captures[member] = raw
        ref = {"archive_member": member, "sha256": hashlib.sha256(raw).hexdigest(), "pointer": "/0"}
        final = copy.deepcopy(original)
        final["source_refs"] = [ref]
        final["closure"] = {"pending_pin": {"reason_code": "no-body", "measurement": "Retain the cited source at an established pin"}}
        rows, _ = merge.reconcile_compact_classes([final], [([original], member, ref["sha256"], "original")], captures)
        row = rows[0]
        self.assertEqual(row["evidence_class"], "UNKNOWN")
        self.assertEqual(row["closure"]["unknown_evidence_reasons"], ["source-review-claim-unpinned"])
        index = {name: {"sha256": hashlib.sha256(data).hexdigest()} for name, data in captures.items()}
        blockers = merge.compact.validate_row(row, index, "start-closure/1")
        self.assertNotIn("unknown-evidence-class", blockers)
        merge.compact.validate_evidence_witness(row, index, captures, {}, blockers, "start-closure/1")
        self.assertEqual([item["reason_code"] for item in row["closure"]["residue"]], ["source-review-claim-unpinned"])
        self.assertTrue(merge.compact.closure_bucket(row, "PENDING-PIN"))
        self.assertFalse(any(item["bucket"] == "G5-F4" for item in row["closure"]["residue"]))
        strict = copy.deepcopy(row)
        strict.pop("closure")
        strict.pop("evidence_class_witness")
        self.assertIn("unknown-evidence-class", merge.compact.validate_row(strict, index))
        action = copy.deepcopy(row)
        action["disposition"] = "TRIAL"
        action.pop("pending")
        action["closure"].pop("residue")
        action["closure"].pop("pending_pin")
        self.assertIn("unknown-evidence-class", merge.compact.validate_row(action, index, "start-closure/1"))

    def test_unknown_skill_claim_residue_uses_final_locator_gap(self):
        from tests.test_compact_manifest import CompactManifestTests
        fixture = CompactManifestTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.native_skill()
        fixture.skill_doc["proposed"][0]["pin"] = "b" * 40
        fixture.rebind_skill_doc()
        original = copy.deepcopy(fixture.rows[0])
        captures = dict(fixture.files)
        member = "inputs/original-skill.json"
        raw = json.dumps([original], sort_keys=True).encode()
        captures[member] = raw
        ref = {"archive_member": member, "sha256": hashlib.sha256(raw).hexdigest(), "pointer": "/0"}
        final = copy.deepcopy(original)
        final["evidence_class"] = "UNKNOWN"
        final["evidence_class_witness"] = ref
        final["source_refs"] = list(final.get("source_refs", [])) + [ref]
        final["primary_sources"][0]["locator"] = "UNKNOWN"
        final["closure"] = {"pending_locator": {"reason_code": "unestablished-pinned-locator", "measurement": "Bind the exact containing-repository locator"},
                            "unknown_evidence_reasons": ["native-skill-entry-witness-unverified"]}
        index = {name: {"sha256": hashlib.sha256(data).hexdigest()} for name, data in captures.items()}
        blockers = []
        merge.compact.validate_evidence_witness(final, index, captures, {}, blockers, "start-closure/1")
        self.assertFalse(blockers)
        self.assertEqual([item["bucket"] for item in final["closure"]["residue"]], ["PENDING-LOCATOR"])
        merge.compact.closure_metadata(final, index)
        self.assertFalse(merge.compact.validate_row(final, index, "start-closure/1", record_residue=False))

    def test_compact_duplicates_preserve_origins_and_exact_role_scope(self):
        row = self.compact_row()
        rows, receipt = merge.merge_compact_groups([
            ([row], "inputs/a.json", "1" * 64, "stars"),
            ([dict(row)], "inputs/b.json", "2" * 64, "fields"),
            ([self.compact_row(role="worker")], "inputs/c.json", "3" * 64, "role"),
        ])
        self.assertEqual(len(rows), 2)
        duplicate = next(x for x in rows if not x["qualification"])
        self.assertEqual(duplicate["disposition"], "WATCH")
        self.assertEqual({x["archive_member"] for x in duplicate["source_refs"]}, {"inputs/a.json", "inputs/b.json"})
        origin = next(x for x in receipt["origins"] if not x["qualification"])
        self.assertEqual(origin["fragments"], ["fields", "stars"])

    def test_compact_pin_or_label_disagreement_stays_pending_without_vote(self):
        a, b = self.compact_row("TRIAL"), self.compact_row("REJECT", "b" * 40)
        b["searched"] = "Pinned README and vendor test source"
        inputs = [([a, a], "inputs/a.json", "1" * 64, "popular"), ([b], "inputs/b.json", "2" * 64, "one-reject")]
        rows, receipt = merge.merge_compact_groups(inputs)
        self.assertEqual(rows[0]["disposition"], "PENDING")
        self.assertEqual(rows[0]["pending"]["provisional_disposition"], "REJECT")
        self.assertEqual(len(rows[0]["primary_sources"]), 2)
        self.assertEqual({x["disposition"] for x in rows[0]["choices"]}, {"TRIAL", "REJECT"})
        self.assertEqual(len(rows[0]["source_refs"]), 3)
        again, _ = merge.merge_compact_groups(list(reversed(inputs)))
        self.assertEqual(rows, again)
        self.assertEqual(len(receipt["pending"]), 1)

    def test_compact_unknown_bundle_and_nested_choices_cannot_disappear(self):
        good = self.compact_row()
        unknown = self.compact_row()
        unknown["primary_sources"][0]["locator"] = "UNKNOWN"
        rows, receipt = merge.merge_compact_groups([([good, unknown], "inputs/rows.json", "a" * 64, "original")])
        self.assertEqual(rows[0]["disposition"], "PENDING")
        self.assertEqual(len(receipt["pending"]), 1)
        self.assertEqual(len(rows[0]["source_refs"]), 2)
        good["choices"] = [{"disposition": "REJECT", "source_refs": [{"archive_member": "captures/reject.json", "sha256": "b" * 64, "pointer": "/row"}]}]
        rows, _ = merge.merge_compact_groups([([good], "inputs/rows.json", "a" * 64, "original")])
        self.assertEqual(rows[0]["disposition"], "PENDING")
        self.assertEqual({x["disposition"] for x in rows[0]["choices"]}, {"REJECT", "WATCH"})

    def test_compact_reserved_origins_and_late_output_symlinks_fail_before_write(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as other:
            root, stage = Path(directory), Path(other) / "asset"
            rows = root / "rows.json"
            sha = write_json(rows, [self.compact_row()])
            manifest = root / "intake.json"
            for member in ("compact/rows.json", "provenance/compact-origin-map.json"):
                write_json(manifest, {"fragments": [{"source": str(rows), "sha256": sha, "archive_member": member, "fragment_id": "original"}]})
                with self.assertRaises(merge.FragmentError):
                    merge.compact_intake([manifest], stage, root, True)
                self.assertFalse(stage.exists())
            stage.mkdir()
            (stage / "provenance").symlink_to(Path(other) / "aliased", target_is_directory=True)
            write_json(manifest, {"fragments": [{"source": str(rows), "sha256": sha, "archive_member": "inputs/rows.json", "fragment_id": "original"}]})
            with self.assertRaises(merge.decisions.InvalidDecisionIndex):
                merge.compact_intake([manifest], stage, root, True)
            self.assertFalse((stage / "inputs").exists())
            self.assertFalse((stage / "compact").exists())

    def test_compact_intake_bad_hash_or_private_capture_fails_before_write(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as other:
            root, stage = Path(directory), Path(other) / "asset"
            rows = root / "rows.json"
            sha = write_json(rows, [self.compact_row()])
            capture = root / "capture.json"
            capture.write_text(str(Path.home()) + "/private-custody")
            manifest = root / "intake.json"
            packet = {"fragments": [{"source": str(rows), "sha256": sha, "archive_member": "inputs/rows.json", "fragment_id": "source"}],
                      "captures": [{"source": str(capture), "sha256": merge.digest(capture.read_bytes()), "archive_member": "captures/source.json"}]}
            write_json(manifest, packet)
            with self.assertRaises(merge.FragmentError):
                merge.compact_intake([manifest], stage, root, True)
            self.assertFalse(stage.exists())
            packet["captures"] = []
            packet["fragments"][0]["sha256"] = "0" * 64
            write_json(manifest, packet)
            with self.assertRaises(merge.FragmentError):
                merge.compact_intake([manifest], stage, root, True)
            self.assertFalse(stage.exists())

    def test_lifecycle_reconciliation_preserves_facts_and_rejects_unreviewed_groups(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            existing = {"repository": "https://github.com/example/existing", "record_types": ["research_supplement"]}
            write_json(root / merge.decisions.INDEX, {"records": [existing]})
            audit = {"components": [{"component_id": "retained", "accepted_scope": "historical"}],
                     "stage_policy": {"stages": ["use", "recovery"]},
                     "counts": {"selected_components": 1, "catalog_identities": 1, "nonselected_catalog_identities": 0,
                                "exclusive_identity_groups": {"research_supplement": 1}, "exclusive_identity_group_scope": "Prior evidence."}}
            write_json(root / merge.LIFECYCLE_TARGET, audit)
            for args in (["git", "init", "-q"], ["git", "add", "."],
                         ["git", "-c", "user.name=G5 synthetic control", "-c", "user.email=g5@example.invalid", "commit", "-qm", "baseline"]):
                subprocess.run(args, cwd=root, capture_output=True, check=True)
            added = {"repository": "https://github.com/example/new", "record_types": ["research_supplement"]}
            write_json(root / merge.decisions.INDEX, {"records": [existing, added]})
            with patch.object(merge.decisions, "validate_index"):
                planned = merge.lifecycle_union(root, "HEAD")
                updated = json.loads(planned[merge.LIFECYCLE_TARGET])
                self.assertEqual(updated["components"], audit["components"])
                self.assertEqual(updated["stage_policy"], audit["stage_policy"])
                self.assertEqual(updated["counts"]["catalog_identities"], 2)
                self.assertEqual(updated["counts"]["exclusive_identity_groups"], {"research_supplement": 2})
                self.assertEqual(updated["g5_catalog_reconciliation"]["added_research_identities"], [added["repository"]])
                self.assertEqual(merge.read_json(root / merge.LIFECYCLE_TARGET), audit)
                added["record_types"] = ["component_record", "research_supplement"]
                write_json(root / merge.decisions.INDEX, {"records": [existing, added]})
                with self.assertRaises(merge.FragmentError):
                    merge.lifecycle_union(root, "HEAD")
                write_json(root / merge.decisions.INDEX, {"records": [added]})
                with self.assertRaises(merge.FragmentError):
                    merge.lifecycle_union(root, "HEAD")
                write_json(root / merge.decisions.INDEX, {"records": [existing]})
                audit["components"][0]["accepted_scope"] = "wrongly changed"
                write_json(root / merge.LIFECYCLE_TARGET, audit)
                with self.assertRaises(merge.FragmentError):
                    merge.lifecycle_union(root, "HEAD")

    def test_scope_splits_do_not_create_global_conflicts(self):
        groups = [
            {"binding": True, "disposition": "REJECT", "lane": "trading", "source_refs": [{"source_id": "a", "pointer": "/rows/0"}]},
            {"binding": True, "disposition": "OUT-OF-SCOPE", "lane": "memory", "source_refs": [{"source_id": "b", "pointer": "/rows/2"}]},
        ]
        overlay = {"records": {
            "a": {"/rows/0": {"row": {"layers": ["execution-broker", "research-factors-ml"]}, "evidence_refs": ["pinned execution source"]}},
            "b": {"/rows/2": {"row": {}, "document": {"layer_id": "durable-memory"}, "evidence_refs": ["pinned memory source"]}},
        }}
        result = merge.normalize_scopes("NoFxAiOS/nofx", groups, overlay)
        self.assertTrue(result["scope_split"])
        self.assertEqual(len(result["rows"]), 3)
        self.assertEqual(result["remainder"], [])

    def test_pure_duplicates_merge_and_keep_every_source_locator(self):
        groups = [{"binding": True, "disposition": "WATCH", "lane": lane,
                   "source_refs": [{"source_id": lane, "pointer": "/rows/7"}]} for lane in ("a", "b")]
        overlay = {"records": {lane: {"/rows/7": {"row": {"layers": ["workers", "native-clients"]},
                                                              "evidence_refs": ["one pinned source"]}} for lane in ("a", "b")}}
        result = merge.normalize_scopes("getpaseo/paseo", groups, overlay)
        self.assertEqual(result["pure_duplicates_merged"], 2)
        self.assertEqual(result["remainder"], [])
        for row in result["rows"]:
            self.assertEqual(len(row["choices"]), 1)
            self.assertEqual({o["source_ref"]["source_id"] for o in row["choices"][0]["observations"]}, {"a", "b"})

    def test_same_slot_conflicts_are_pending_without_votes_or_adoption(self):
        groups = [{"binding": True, "disposition": label, "lane": lane,
                   "source_refs": [{"source_id": lane, "pointer": "/row"}]} for lane, label in
                  [("a", "ADOPT-NOW"), ("b", "ADOPT-NOW"), ("c", "TRIAL"), ("d", "REJECT")]]
        overlay = {"records": {lane: {"/row": {"row": {"layer_id": "workers"}, "evidence_refs": [lane + " pinned source"]}}
                               for lane in ("a", "b", "c", "d")}}
        result = merge.normalize_scopes("example/project", groups, overlay)
        row = result["remainder"][0]
        self.assertEqual(row["status"], "PENDING")
        self.assertEqual(row["provisional_disposition"], "REJECT")
        self.assertIsNone(row["disposition"])
        self.assertEqual(len(row["choices"]), 3)
        self.assertTrue(row["settling_measurement"])
        self.assertEqual(row["measurement_owner"], "grand-catalog")

    def test_unknown_scope_is_not_inferred_from_prose_or_nonbinding_screens(self):
        groups = [
            {"binding": True, "disposition": "WATCH", "scope": "workers and native clients", "source_refs": [{"source_id": "a", "pointer": "/row"}]},
            {"binding": False, "disposition": "REJECT", "source_refs": [{"source_id": "b", "pointer": "/row"}]},
        ]
        overlay = {"records": {"a": {"/row": {"row": {"scope": "workers and native clients"}}}}}
        result = merge.normalize_scopes("example/project", groups, overlay)
        self.assertEqual(result["rows"], [])
        self.assertEqual(len(result["unknown_scope_claims"]), 1)
        self.assertEqual(result["remainder"][0]["slot"], "UNKNOWN")
        self.assertEqual(result["remainder"][0]["provisional_disposition"], "WATCH")

    def test_native_scope_overlay_preserves_original_ancestor_and_hash_fields(self):
        overlay = {"sources": {"input-001": {
            "original_input_sha256": "a" * 64, "published_scope_records_sha256": "b" * 64,
            "selected_records": {"/rows/2": {"explicit_scope": {}, "status": "explicit_document_scope",
                "inherited_explicit_scope": [{"ancestor_pointer": "", "scope": {"layer_id": "durable-memory", "catalog": "foundation"}}]}},
        }}}
        groups = [{"binding": True, "disposition": "OUT-OF-SCOPE", "source_refs": [{"source_id": "input-001", "pointer": "/rows/2"}]}]
        result = merge.normalize_scopes("example/project", groups, overlay)
        self.assertEqual(result["rows"][0]["slot"], "durable-memory")
        observed = result["rows"][0]["choices"][0]["observations"][0]
        self.assertEqual(observed["evidence"][0]["original_input_sha256"], "a" * 64)
        self.assertEqual(observed["source_scope"]["document"]["catalog"], "foundation")
        source = overlay["sources"]["input-001"]
        source["inherited_explicit_scope"] = {"/": {"layer_id": "durable-memory", "catalog": "foundation"}}
        source["selected_records"]["/rows/2"]["inherited_explicit_scope"] = ["/"]
        source["selected_records"]["/rows/2"]["scope_authority_status"] = "explicit_document_scope"
        self.assertEqual(merge.normalize_scopes("example/project", groups, overlay)["rows"][0]["slot"], "durable-memory")
        source["selected_records"]["/rows/2"]["scope_authority_status"] = "PENDING_EXPLICIT_FIELD_BINDING"
        pending = merge.normalize_scopes("example/project", groups, overlay)["rows"][0]
        self.assertEqual(pending["status"], "PENDING")
        self.assertIsNone(pending["disposition"])
        self.assertEqual(pending["choices"][0]["observations"][0]["scope_authority_status"], "PENDING_EXPLICIT_FIELD_BINDING")
        bound = merge.normalize_scopes("example/project", groups, overlay, {"durable-memory"})["rows"][0]
        self.assertEqual(bound["status"], "SOURCE-REVIEW")
        observation = bound["choices"][0]["observations"][0]
        self.assertEqual(observation["scope_authority_status"], "PENDING_EXPLICIT_FIELD_BINDING")
        self.assertEqual(observation["source_field_binding"], "BOUND_TO_COMMITTED_SELECTORS")
        unknown = merge.normalize_scopes("example/project", groups, overlay, {"workers"})["rows"][0]
        self.assertEqual(unknown["status"], "PENDING")
        source["selected_records"]["/rows/2"]["scope_authority_status"] = "PENDING_UNKNOWN_FIELD_SCOPE"
        self.assertEqual(merge.normalize_scopes("example/project", groups, overlay, {"durable-memory"})["rows"][0]["status"], "PENDING")

    def test_remainder_snapshots_change_paths_without_rewriting_prior_evidence(self):
        first = merge.remainder_files([])
        row = {"repository": "example/project", "slot": "UNKNOWN", "choices": [{"disposition": "WATCH"}],
               "qualification": {}, "provisional_disposition": "WATCH", "settling_measurement": "Read exact source", "measurement_owner": "grand-catalog"}
        second = merge.remainder_files([row])
        self.assertFalse(set(first) & set(second))
        self.assertEqual(first, merge.remainder_files([]))

    def test_wrong_hash_preflights_before_any_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "a.json"
            second = root / "b.json"
            first_hash = write_json(first, {"checked": True})
            write_json(second, {"checked": False})
            manifest = root / "fragment.json"
            write_json(manifest, {"files": [
                {"target": "catalogs/landscape/a.json", "source": str(first), "sha256": first_hash},
                {"target": "catalogs/landscape/b.json", "source": str(second), "sha256": "0" * 64},
            ]})
            self.assertEqual(merge.main(["--root", str(root), "--manifest", str(manifest), "--write"]), 2)
            self.assertFalse((root / "catalogs").exists())

    def test_targets_cannot_escape_or_replace_saturation_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for target in ("../escaped.json", "/tmp/escaped.json", "catalogs/saturation/ledger.json",
                           "catalogs/landscape/./foundation.json", "catalogs/landscape//foundation.json"):
                with self.subTest(target=target), self.assertRaises(merge.FragmentError):
                    merge.target_path(root, target)

    def test_symlink_ancestor_cannot_escape(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as other:
            root = Path(directory)
            (root / "docs").symlink_to(Path(other), target_is_directory=True)
            with self.assertRaises(merge.FragmentError):
                merge.target_path(root, "docs/escaped.md")

    def test_internal_symlink_cannot_alias_protected_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            write_json(root / "manifests/stack.json", {"protected": True})
            (root / "docs/alias.md").symlink_to(root / "manifests/stack.json")
            with self.assertRaises(merge.FragmentError):
                merge.target_path(root, "docs/alias.md")

    def test_historical_verdict_and_identity_changes_are_rejected(self):
        row = {"layer_id": "workers", "winners": [{"component_id": "codex"}], "lanes": {"agreement": "same_winner"}}
        before = {"layers": [row]}
        changed = {"layers": [{**row, "winners": [{"component_id": "new-default"}]}]}
        with self.assertRaises(merge.FragmentError):
            merge.preserve_verdicts(before, changed, "catalogs/landscape/foundation.json")
        with self.assertRaises(merge.FragmentError):
            merge.preserve_verdicts(before, {"layers": []}, "catalogs/landscape/foundation.json")
        merge.preserve_verdicts(before, {"layers": [{**row, "source_note": "new source"}]}, "catalogs/landscape/foundation.json")

    def test_defaults_candidate_history_and_duplicate_layers_are_protected(self):
        row = {"layer_id": "workers", "current_choice": "codex", "decision": "retained",
               "candidates": [{"repository": "example/project", "rationale": "prior evidence"}]}
        before = {"schema_version": 2, "layers": [row]}
        for changed in (
            [],
            None,
            {"schema_version": 3, "layers": [row]},
            {"schema_version": 2, "layers": [{**row, "current_choice": "another"}]},
            {"schema_version": 2, "layers": [{**row, "decision": "new"}]},
            {"schema_version": 2, "layers": [{**row, "candidates": []}]},
            {"schema_version": 2, "layers": [row, row]},
        ):
            with self.subTest(changed=changed), self.assertRaises(merge.FragmentError):
                merge.preserve_verdicts(before, changed, "catalogs/landscape/foundation.json")

    def test_json_checks_use_target_extension_even_for_text_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = {"layer_id": "workers", "current_choice": "codex"}
            write_json(root / "catalogs/landscape/foundation.json", {"layers": [row]})
            source = root / "fragment.txt"
            sha = write_json(source, {"layers": [{**row, "current_choice": "changed"}]})
            manifest = root / "manifest.json"
            write_json(manifest, {"files": [{"target": "catalogs/landscape/foundation.json", "source": str(source), "sha256": sha}]})
            with self.assertRaises(merge.FragmentError):
                merge.manifest_files(root, manifest)

    def test_frozen_guard_uses_head_when_working_file_missing_or_changed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "fragment.txt"
            sha = write_json(source, {"rewritten": True})
            manifest = root / "manifest.json"
            relative = "evidence/artifacts/g5-frozen/source.txt"
            write_json(manifest, {"files": [{"target": relative, "source": str(source), "sha256": sha}]})
            with patch.object(merge, "committed_bytes", return_value=b"frozen historical bytes"):
                for exists in (False, True):
                    if exists:
                        target = root / relative
                        target.parent.mkdir(parents=True)
                        target.write_bytes(source.read_bytes())
                    with self.subTest(exists=exists), self.assertRaises(merge.FragmentError):
                        merge.manifest_files(root, manifest)

    def test_invalid_supplement_fails_before_targets_or_registry_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "fragment.json"
            sha = write_json(source, {"checked": True})
            manifest = root / "manifest.json"
            write_json(manifest, {"files": [{"target": "catalogs/landscape/test.json", "source": str(source), "sha256": sha}]})
            write_json(root / merge.decisions.MANIFEST, {})
            write_json(root / merge.decisions.INDEX, {"sources": []})
            with patch.object(merge, "register_file") as registry:
                self.assertEqual(merge.main(["--root", str(root), "--manifest", str(manifest), "--write",
                                             "--supplement", "evidence/artifacts/g5-missing/rows.json#/collection"]), 2)
                registry.assert_not_called()
            self.assertFalse((root / "catalogs/landscape/test.json").exists())

    def test_pending_star_conflict_keeps_all_claims_without_a_final_class(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root / merge.STAR_TARGET, {"schema_version": 1, "repositories": [], "count": 0})
            metadata = root / "metadata.json"
            rows = [{"repository": f"example/project{index}", "license_metadata": {"spdx_id": "MIT"}} for index in range(368)]
            metadata.write_text(json.dumps(rows[:100]) + "\n" + json.dumps(rows[100:]), encoding="utf-8")
            fragment = root / "stars.json"
            claims = [{"repository": row["repository"], "disposition": "WATCH", "status": "SOURCE-REVIEW",
                       "evidence_refs": [row["repository"] + "@" + "a" * 40 + ":README.md:1"],
                       "source_decisions": [{"scope": "global starred inventory", "disposition": "WATCH"}]} for row in rows]
            claims[0].update(disposition="REJECT", status="PENDING", conflicts=["WATCH", "REJECT"],
                             source_decisions=[{"scope": "leaf only"}, {"scope": "global review owed"}])
            sha = write_json(fragment, {"repositories": claims})
            output, summary = merge.stars_document(root, fragment, sha, metadata, merge.digest(metadata.read_bytes()))
            self.assertEqual(summary["stars"], 367)
            self.assertIsNone(output["repositories"][0]["disposition"])
            self.assertEqual(output["repositories"][0]["proposed_disposition"], "REJECT")
            self.assertEqual(output["repositories"][0]["source_decisions"], claims[0]["source_decisions"])
            self.assertEqual(output["repositories"][1]["license_metadata"], "MIT")
            again, _ = merge.stars_document(root, fragment, sha, metadata, merge.digest(metadata.read_bytes()))
            self.assertEqual(merge.json_text(output, indent=2), merge.json_text(again, indent=2))
            claims[1]["repository"] = claims[0]["repository"]
            sha = write_json(fragment, {"repositories": claims})
            with self.assertRaises(merge.FragmentError):
                merge.stars_document(root, fragment, sha, metadata, merge.digest(metadata.read_bytes()))

    def test_empty_evidence_or_unknown_status_cannot_bind_star_class(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root / merge.STAR_TARGET, {"repositories": []})
            metadata = root / "metadata.json"
            rows = [{"repository": f"example/project{index}"} for index in range(368)]
            metadata_sha = write_json(metadata, rows)
            claims = [{"repository": row["repository"], "disposition": "WATCH", "status": "SOURCE-REVIEW",
                       "evidence_refs": [], "source_decisions": []} for row in rows]
            claims[0].update(status="INCOMPLETE", evidence_refs=["a source"], source_decisions=[{}])
            fragment = root / "stars.json"
            sha = write_json(fragment, {"rows": claims, "input_manifest": {"source_ids": {"input-001": {"sha256": "a" * 64}}}})
            output, summary = merge.stars_document(root, fragment, sha, metadata, metadata_sha)
            self.assertEqual(summary["stars"], 0)
            self.assertTrue(all(row["disposition"] is None for row in output["repositories"]))
            self.assertIn("input-001", output["g5"]["input_manifest"]["source_ids"])
            claims[0].update(conflicts=[], conflict=["WATCH", "REJECT"])
            sha = write_json(fragment, {"rows": claims})
            with self.assertRaises(merge.FragmentError):
                merge.stars_document(root, fragment, sha, metadata, metadata_sha)
            claims[0] = {"repository": rows[0]["repository"], "disposition": ["WATCH"]}
            sha = write_json(fragment, {"rows": claims})
            with self.assertRaises(merge.FragmentError):
                merge.stars_document(root, fragment, sha, metadata, metadata_sha)

    def test_malformed_packet_errors_are_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for value in ([], {"files": [None]}, {"files": [{"target": None, "source": "x", "sha256": None}]}):
                manifest = root / "manifest.json"
                write_json(manifest, value)
                with self.subTest(value=value):
                    self.assertEqual(merge.main(["--root", str(root), "--manifest", str(manifest)]), 2)


if __name__ == "__main__":
    unittest.main()
