"""Local synthetic integrity controls for the G5 data binder, not native acceptance."""
from __future__ import annotations

import hashlib
import importlib.util
import json
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
