"""Meaningful source and observation boundaries for architecture pages."""

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from tests.local_pages_architecture_policy_fixture import G5, policy_fixture


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("architecture_sources", ROOT / "tools/local-pages/architecture_sources.py")
sources = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sources)
EVIDENCE_SPEC = importlib.util.spec_from_file_location("architecture_evidence", ROOT / "tools/local-pages/architecture_evidence.py")
evidence = importlib.util.module_from_spec(EVIDENCE_SPEC)
EVIDENCE_SPEC.loader.exec_module(evidence)


class ArchitectureSourcesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name)
        self.root, self.state = base / "repo", base / "state"
        self.asset = self.state / G5
        self.asset.parent.mkdir(parents=True, exist_ok=True)
        self.policy_path = policy_fixture(base / "independent-policy.json")
        for module in (sources, evidence):
            approved = patch.object(module, "SOURCE_POLICY_PATH", self.policy_path)
            approved.start()
            self.addCleanup(approved.stop)
        self.write(self.root, "catalogs/landscape/manifest.json", {"catalogs": {"foundation": "catalogs/landscape/foundation.json", "us-equities": "catalogs/landscape/us-equities.json"}})
        self.foundation = {"layers": [self.layer("instructions-skills", "https://github.com/anthropics/skills")]}
        self.trading = {"layers": [self.layer("market-data-reference", "https://github.com/alpacahq/alpaca-py")]}
        self.write(self.root, "catalogs/landscape/foundation.json", self.foundation)
        self.write(self.root, "catalogs/landscape/us-equities.json", self.trading)
        self.cc = {"schema": "cc-now/1", "updated_utc": "2026-10-09T01:14:12Z", "gates": [{"id": "G5", "state": "CHECK PASSING; READS PENDING"}], "adoption_program": {"rule": "PRIVATE-RULE", "layers": [{"layer": "Skills", "owner": "PRIVATE-OWNER", "state": "proposed"}], "stages": ["installed", "invoked", "measured", "accepted"]}}
        self.write(self.state, "coordination/command-center/pages/cc-now.json", self.cc)
        self.records = [self.g5_row("anthropics/skills"), self.g5_row("other/project"), self.g5_row("new/project", catalog="us-equities", slot="market-data-reference")]
        self.encode_asset(self.records)

    def write(self, root, relative, value):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def layer(self, layer_id, repository):
        return {"layer_id": layer_id, "title": layer_id, "current_choice": "dated selected choice", "decision": "retain", "verdict_status": "native proven", "checked_at": "2026-09-22", "rationale": "retained source rationale", "winners": [{"name": "Selected source", "repository": repository, "pin": "v1.2.3", "why_selected": "measured native result", "evidence_class": "native_proven"}], "candidates": [{"name": "candidate", "repository": "https://github.com/candidate/project", "disposition": "rejected", "rationale": "failed source requirement"}], "alternatives": [{"name": "alternative", "repository": "https://github.com/alternative/project", "disposition": "conditional", "why_not_default": "unmeasured native scope"}], "evidence_refs": ["docs/source-receipt.md"]}

    def g5_row(self, repository, *, catalog="skills", slot="skills-mcp-build"):
        return {"repository_or_entry": repository, "slot": slot, "qualification": {"catalog": catalog, "slot": slot}, "disposition": "TRIAL", "evidence_class": "SOURCE-REVIEW", "pin": {"kind": "commit", "repository_or_source": repository, "subject": "implementation", "version_or_commit": "a" * 40}, "primary_sources": [{"locator": f"https://github.com/{repository}", "refresh_date": "2026-10-08"}], "pending": {"status": "PENDING", "measurement": "native task not measured"}, "decision_scope": "source review", "refresh_date": "2026-10-08", "task": "PRIVATE-TASK", "prompt": "PRIVATE-PROMPT"}

    def encode_asset(self, records):
        raw = json.dumps(records, ensure_ascii=False).encode()
        self.raw_rows = raw
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            info = tarfile.TarInfo("compact/rows.json")
            info.size = len(raw)
            archive.addfile(info, io.BytesIO(raw))
            forbidden = b"PRIVATE-UNNEEDED-MEMBER\xff"
            info = tarfile.TarInfo("private/prompts/ignored.json")
            info.size = len(forbidden)
            archive.addfile(info, io.BytesIO(forbidden))
        process = subprocess.run(["/usr/bin/zstd", "-q", "-c"], input=buffer.getvalue(), capture_output=True, timeout=20, check=True)
        self.asset.write_bytes(process.stdout)

    def build(self):
        return sources.build(self.root, self.state, self.asset)

    def test_canonical_count_comes_only_from_manifest_catalogs(self):
        self.write(self.root, "catalogs/landscape/supplement.json", {"layers": [self.layer("foreign-layer", "https://github.com/foreign/project")] * 7})
        model = self.build()
        self.assertEqual(model["layer_count"], 2)
        self.assertEqual([row["key"] for row in model["layers"]], ["foundation:instructions-skills", "us-equities:market-data-reference"])

    def test_dated_choices_keep_reasons_pins_and_rejections(self):
        self.cc["adoption_program"]["layers"][0]["state"] = "replace every tool"
        self.write(self.state, "coordination/command-center/pages/cc-now.json", self.cc)
        row = self.build()["layers"][0]
        self.assertEqual(row["current_choice"], "dated selected choice")
        self.assertEqual(row["winners"][0]["pin"], "v1.2.3")
        self.assertEqual(row["winners"][0]["why_selected"], "measured native result")
        self.assertEqual(row["alternatives"][0]["why_not_default"], "unmeasured native scope")
        self.assertEqual(row["rejected"][0]["rationale"], "failed source requirement")
        self.assertEqual(row["adoption_stage"], "UNREPORTED")
        self.assertEqual(row["source_choice"]["checked_at"], "2026-09-22")

    def test_g5_exact_repository_and_layer_matches_leave_others_unmatched(self):
        self.records.append(self.g5_row("anthropics/skills-looks-similar"))
        self.encode_asset(self.records)
        model = self.build()
        self.assertEqual(model["g5"]["rows"], 4)
        self.assertEqual(model["g5"]["matched_rows"], 2)
        self.assertEqual(model["g5"]["unmatched_rows"], 2)
        self.assertEqual(len(model["layers"][0]["g5_candidates"]), 1)
        self.assertEqual(len(model["layers"][1]["g5_candidates"]), 1)
        self.assertNotIn("other/project", json.dumps(model))

    def test_partial_gate_state_does_not_promote_grand_candidates(self):
        model = self.build()
        self.assertEqual(model["g5"]["status"], "candidate, PENDING G5")
        self.assertFalse(model["g5"]["accepted"])
        row = model["layers"][0]["g5_candidates"][0]
        self.assertFalse(row["accepted"])
        self.assertEqual(row["recorded_disposition"], "TRIAL")
        self.assertEqual(row["status"], "candidate, PENDING G5")

    def test_even_a_met_gate_does_not_create_per_candidate_acceptance(self):
        self.cc["gates"][0]["state"] = "MET"
        self.write(self.state, "coordination/command-center/pages/cc-now.json", self.cc)
        model = self.build()
        self.assertEqual(model["g5"]["status"], "G5 MET in current view")
        self.assertFalse(model["layers"][0]["g5_candidates"][0]["accepted"])
        self.assertEqual(model["layers"][0]["adoption_stage"], "UNREPORTED")

    def test_actual_asset_and_member_hashes_are_reproduced(self):
        model = self.build()
        receipt = next(item for item in model["sources"] if item.get("member"))
        self.assertEqual(receipt["sha256"], hashlib.sha256(self.asset.read_bytes()).hexdigest())
        self.assertEqual(receipt["member_sha256"], hashlib.sha256(self.raw_rows).hexdigest())
        self.assertEqual(receipt["member_bytes"], len(self.raw_rows))
        self.assertIn("file_utc", receipt)

    def test_unneeded_members_and_free_text_do_not_enter_projection(self):
        self.records[0]["pending"]["owner"] = "PRIVATE-OWNER"
        self.records[0]["primary_sources"].append({"locator": "https://github.com/anthropics/skills?token=private", "prompt": "PRIVATE-PROMPT"})
        self.records[0]["pin"]["version_or_commit"] = "operator@example.test"
        self.records[0]["decision_scope"] = "Bearer fixturecredentiallongvalue"
        self.encode_asset(self.records)
        model = self.build()
        serialized = json.dumps(model)
        for value in ["PRIVATE-OWNER", "PRIVATE-TASK", "PRIVATE-PROMPT", "PRIVATE-RULE", "PRIVATE-UNNEEDED-MEMBER", "operator@example.test", "fixturecredentiallongvalue", "token=private"]:
            self.assertNotIn(value, serialized)

    def test_record_size_bound_and_unicode_stream_boundaries(self):
        self.records[0]["note"] = "é" * 6000
        self.encode_asset(self.records)
        self.assertEqual(self.build()["g5"]["rows"], 3)
        self.records[0]["note"] = "x" * (sources._RECORD_LIMIT + 1)
        self.encode_asset(self.records)
        with self.assertRaises(ValueError):
            self.build()

    def test_supplement_quality_is_joined_by_explicit_identity_only(self):
        self.write(self.root, "catalogs/landscape/upstream-snapshot.json", {"components": [{"repository": "https://github.com/anthropics/skills", "selected_version": "v1", "archived": False, "latest_stable_release": {"tag_name": "v2", "published_at": "2026-10-08", "prompt": "PRIVATE-PROMPT"}}, {"repository": "https://github.com/anthropics/skills-looks-similar", "selected_version": "v3"}]})
        quality = self.build()["layers"][0]["source_quality"]
        self.assertEqual(len(quality), 1)
        self.assertEqual(quality[0]["latest_stable_release"]["tag_name"], "v2")
        self.assertNotIn("prompt", quality[0]["latest_stable_release"])

    def test_native_adoption_observations_do_not_fill_per_tool_stages(self):
        self.write(self.state, "coordination/command-center/pages/adoption-now.json", {"schema": "adoption-now/1", "generated_utc": "2026-10-09T01:00:00Z", "window_hours": 24, "orchestration": {"claude_by_role": {}, "codex_by_lane": {}, "unmeasured": ["SDK jobs"], "prompt": "PRIVATE-PROMPT"}})
        self.immutable_snapshot("2026-10-09T00:31:25Z", orchestration={"claude_by_role": {}, "codex_by_lane": {}, "unmeasured": ["SDK jobs"]})
        model = self.build()
        self.assertEqual(model["adoption_program"]["global_stages"], ["installed", "invoked", "measured", "accepted"])
        self.assertTrue(model["adoption_observation"]["orchestration_published"])
        self.assertTrue(all(row["adoption_stage"] == "UNREPORTED" for row in model["layers"]))

    def immutable_snapshot(self, generated, calls=5, **extra):
        document = {"schema": "adoption-now/1", "generated_utc": generated, "window_hours": 24, "claude_by_role": {"native-agent-stack-1a": {"sessions": 1, "servers": {"plugin_context-mode_context-mode": {"calls": calls, "sessions": 1}, "context-mode": {"calls": 2, "sessions": 1}}}}, "codex_by_lane": {}, **extra}
        raw = json.dumps(document).encode()
        digest = hashlib.sha256(raw).hexdigest()
        directory = self.state / "coordination/ns2604-coop/notes/adoption-evidence-20261008"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"adoption-now-{digest[:16]}.json"
        path.write_bytes(raw)
        return path, digest

    def test_newest_hash_verified_snapshot_is_chosen_by_observation_time(self):
        self.immutable_snapshot("2026-10-08T22:00:00Z")
        expected, digest = self.immutable_snapshot("2026-10-09T00:31:25Z")
        directory = expected.parent
        (directory / "adoption-now-aaaaaaaaaaaaaaaa.json").write_text(json.dumps({"schema": "adoption-now/1", "generated_utc": "2026-10-10T00:00:00Z", "window_hours": 24}))
        self.immutable_snapshot("2026-10-11T00:00:00", calls=100)
        observation = evidence.invocation_source(self.state)
        self.assertEqual(observation["path"], str(expected))
        self.assertEqual(observation["sha256"], digest)
        self.assertEqual(observation["generated_utc"], "2026-10-09T00:31:25Z")
        self.assertEqual(observation["roles"][0]["name"], "owner session (reports to CC)")

    def test_invocations_exact_alias_counts_once_and_unknown_is_not_zero(self):
        self.immutable_snapshot("2026-10-09T00:31:25Z")
        observation = evidence.invocation_source(self.state)
        exact = evidence._invoke({"component_id": "context-mode"}, observation)
        self.assertEqual(exact["calls"], 7)
        self.assertEqual(len(exact["roles"]), 2)
        self.assertEqual(exact["roles"][0]["sessions"], 1)
        self.assertEqual(exact["roles"][0]["window_hours"], 24)
        unknown = evidence._invoke({"component_id": "context-mode-similar"}, observation)
        self.assertIsNone(unknown["calls"])
        self.immutable_snapshot("2026-10-09T01:31:25Z", calls=None)
        self.assertIsNone(evidence._invoke({"component_id": "context-mode"}, evidence.invocation_source(self.state))["calls"])

    def receipt_component(self, *, evidence_class="native_proven", kind="upstream_e2e", **changes):
        relative = "evidence/receipts/exact-fixture.json"
        receipt = {"component_id": "context-mode", "kind": kind, "evidence_class": evidence_class, "observed_at_utc": "2026-10-08T21:00:00Z", "result": "pass", "command": "npm run upstream-e2e", "pin": "v1", **changes}
        path = self.write(self.root, relative, receipt)
        return {"component_id": "context-mode", "pin": "v1", "evidence_class": evidence_class, "evidence_refs": [relative]}, path

    def test_e2e_requires_exact_receipt_class_harness_result_and_identity(self):
        component, path = self.receipt_component()
        e2e = evidence._e2e(self.root, component, [], "matrix")
        self.assertTrue(e2e["verified"])
        self.assertEqual(e2e["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(e2e["date"], "2026-10-08T21:00:00Z")
        self.assertEqual(e2e["command"], "npm run upstream-e2e")
        for changes in [{"evidence_class": "source_review"}, {"evidence_class": "native_execution"}, {"kind": "native_installation"}, {"command": None}, {"result": "failure"}, {"result": {"status": "pass"}}, {"component_id": "other-tool"}, {"pin": "v2"}, {"pin": None}, {"observed_at_utc": "not a date"}]:
            component, path = self.receipt_component(**changes)
            e2e = evidence._e2e(self.root, component, [], "matrix")
            self.assertFalse(e2e["verified"], changes)
            self.assertEqual(e2e["status"], "no upstream E2E evidence")

    def test_recorded_invocations_alone_do_not_complete_e2e_evidence(self):
        self.immutable_snapshot("2026-10-09T00:31:25Z")
        component, _ = self.receipt_component(evidence_class="local_integration", kind="native_installation")
        layer = {"key": "foundation:token-efficiency", "winners": [component]}
        evidence.enrich(self.root, self.state, [layer])
        self.assertTrue(layer["organic_invocation_positive"])
        self.assertFalse(layer["verified_upstream_e2e"])
        self.assertFalse(layer["evidence_complete"])

    def test_declared_local_integration_e2e_keeps_its_original_class(self):
        component, path = self.receipt_component(evidence_class="local_integration")
        result = evidence._e2e(self.root, component, [], "matrix")
        self.assertTrue(result["verified"])
        self.assertEqual(result["evidence_class"], "local_integration")
        self.assertEqual(result["class_source"], path.relative_to(self.root).as_posix())
        self.assertEqual(result["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        component, _ = self.receipt_component(evidence_class="local_integration", kind="native_installation")
        self.assertFalse(evidence._e2e(self.root, component, [], "matrix")["verified"])

    def test_invocation_and_e2e_on_different_components_do_not_combine(self):
        self.immutable_snapshot("2026-10-09T00:31:25Z")
        component, path = self.receipt_component(component_id="other-tool")
        component["component_id"] = "other-tool"
        layer = {"key": "foundation:token-efficiency", "winners": [{"component_id": "context-mode"}, component]}
        evidence.enrich(self.root, self.state, [layer])
        self.assertTrue(layer["organic_invocation_positive"])
        self.assertTrue(layer["verified_upstream_e2e"])
        self.assertFalse(layer["evidence_complete"])

    def test_immutable_role_projection_excludes_prompts_and_email_labels(self):
        self.immutable_snapshot("2026-10-09T00:31:25Z", codex_by_lane={"operator@example.test": {"conversations": 1, "servers": {"serena": {"calls": 1, "conversations": 1}}, "prompt": "PRIVATE-PROMPT"}})
        observation = evidence.invocation_source(self.state)
        self.assertNotIn("operator@example.test", json.dumps(observation))
        self.assertNotIn("PRIVATE-PROMPT", json.dumps(observation))

    def test_inventory_attachment_uses_built_metadata_without_receipt_reads(self):
        self.immutable_snapshot("2026-10-09T00:31:25Z")
        component, path = self.receipt_component()
        layer = {"key": "foundation:token-efficiency", "winners": [component]}
        evidence.enrich(self.root, self.state, [layer])
        index = evidence.evidence_index([layer])
        path.unlink()
        items = [{"component_id": "context-mode"}, {"component_id": "context-mode-other"}]
        evidence.attach_inventory(items, index)
        self.assertTrue(items[0]["evidence_complete"])
        self.assertFalse(items[1]["evidence_complete"])
        self.assertEqual(items[1]["e2e"]["status"], "no upstream E2E evidence")

    def registered_receipt(self, relative="evidence/hosts/fixture/receipt.json", **changes):
        doc = {"component_id": "context-mode", "pin": "v1", "kind": "upstream_e2e", "evidence_class": "native_proven", "observed_at_utc": "2026-10-08T21:00:00Z", "result": "pass", "command": "npm run upstream-e2e", **changes}
        path = self.write(self.root, relative, doc)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.write(self.root, "manifests/evidence.json", {"files": [{"path": relative, "sha256": digest, "bytes": path.stat().st_size}]})
        return path, digest

    def test_registered_native_receipt_binds_without_canonical_reference(self):
        path, digest = self.registered_receipt()
        index = evidence._EvidenceSources(self.root)
        component = {"component_id": "context-mode", "pin": "v1"}
        result = evidence._e2e(self.root, component, [], "matrix", index)
        self.assertTrue(result["verified"])
        self.assertEqual(result["source_tier"], "host registry")
        self.assertEqual(result["sha256"], digest)
        self.assertEqual(index.stats["registry_verified"], 1)

    def test_stale_registry_hash_cannot_be_bypassed_by_explicit_reference(self):
        path, digest = self.registered_receipt()
        changed = json.loads(path.read_text())
        changed["command"] = "npm run changed-e2e"
        path.write_text(json.dumps(changed))
        index = evidence._EvidenceSources(self.root)
        component = {"component_id": "context-mode", "pin": "v1", "evidence_refs": [path.relative_to(self.root).as_posix()]}
        self.assertFalse(evidence._e2e(self.root, component, [], "matrix", index)["verified"])
        self.assertEqual(index.stats["registry_digest_mismatch"], 1)

    def test_matrix_pointer_breaks_tie_with_other_registered_proof(self):
        self.registered_receipt()
        direct = "evidence/receipts/matrix-e2e.json"
        self.write(self.root, direct, {"component_id": "context-mode", "pin": "v1", "kind": "upstream_e2e", "evidence_class": "native_proven", "observed_at_utc": "2026-10-08T21:00:00Z", "result": "pass", "command": "npm run matrix-e2e"})
        index = evidence._EvidenceSources(self.root)
        component = {"component_id": "context-mode", "pin": "v1"}
        matrix = [{"component_id": "context-mode", "evidence_class": "native_proven", "receipt_path": direct}]
        result = evidence._e2e(self.root, component, matrix, "matrix", index)
        self.assertEqual(result["path"], direct)
        self.assertEqual(result["source_tier"], "component matrix")

    def test_latest_qualifying_observation_is_independent_of_receipt_order(self):
        older = "evidence/receipts/older.json"
        newer = "evidence/receipts/newer.json"
        for path, date in [(older, "2026-10-07T21:00:00Z"), (newer, "2026-10-08T21:00:00Z")]:
            self.write(self.root, path, {"component_id": "context-mode", "pin": "v1", "kind": "upstream_e2e", "evidence_class": "native_proven", "observed_at_utc": date, "result": "pass", "command": "npm run exact-e2e"})
        for order in [[older, newer], [newer, older]]:
            component = {"component_id": "context-mode", "pin": "v1", "evidence_refs": order}
            result = evidence._e2e(self.root, component, [], "matrix")
            self.assertEqual(result["path"], newer)
            self.assertEqual(result["date"], "2026-10-08T21:00:00Z")
        changed = json.loads((self.root / newer).read_text())
        changed["observed_at_utc"] = "2026-10-08T21:00:00"
        self.write(self.root, newer, changed)
        component = {"component_id": "context-mode", "pin": "v1", "evidence_refs": [newer]}
        self.assertFalse(evidence._e2e(self.root, component, [], "matrix")["verified"])

    def test_readiness_fresh_pointer_requires_recorded_status_and_hash(self):
        path = self.write(self.root, "evidence/artifacts/exact/receipt.json", {"component_id": "context-mode", "pin": "v1", "kind": "upstream_e2e", "evidence_class": "native_proven", "observed_at_utc": "2026-10-08T21:00:00Z", "result": "pass", "command": "npm run exact-e2e"})
        field = {"status": "VERIFIED", "value": True, "receipt": {"root": "repo", "path": path.relative_to(self.root).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}}
        readiness = {"layers": [{"id": "token-efficiency", "selected_tools": [{"fields": {"component_id": {"value": "context-mode"}, "repository": {"value": "https://github.com/mksglu/context-mode"}, "fresh_session_invoke": field}}]}]}
        self.write(self.root, "catalogs/north-star/readiness.json", readiness)
        component = {"component_id": "context-mode", "pin": "v1"}
        result = evidence._e2e(self.root, component, [], "matrix", evidence._EvidenceSources(self.root))
        self.assertTrue(result["verified"])
        self.assertEqual(result["source_tier"], "readiness Fresh invocation")
        field["status"] = "UNVERIFIED"
        self.write(self.root, "catalogs/north-star/readiness.json", readiness)
        self.assertFalse(evidence._e2e(self.root, component, [], "matrix", evidence._EvidenceSources(self.root))["verified"])

    def test_absent_g5_quality_is_unreported_not_positive_measurement(self):
        row = sources._g5_row(self.g5_row("anthropics/skills"), "asset#/compact/rows.json", False)
        quality = row["quality_evidence"]
        for category in ("maintenance", "releases", "tests", "benchmarks"):
            self.assertEqual(quality[category], {"status": "UNREPORTED", "fields": {}})
        self.assertEqual(quality["qualification"]["catalog"], "skills")
        self.assertEqual(row["status"], "candidate, PENDING G5")
        self.assertFalse(row["accepted"])

    def test_recorded_g5_quality_selects_fields_and_retains_actual_provenance(self):
        record = self.g5_row("anthropics/skills")
        record.update({"maintenance": {"status": "source-reviewed", "pushed_at": "2026-10-08", "prompt": "PRIVATE-PROMPT"}, "releases": [{"tag_name": "v1", "published_at": "2026-10-08", "task": "PRIVATE-TASK"}], "benchmarks": {"status": "unmeasured", "evidence_class": "SOURCE-REVIEW", "prompt": "PRIVATE-PROMPT"}, "tests": None, "source_entry_witness": {"archive_member": "safe/catalog.json", "pointer": "/entries/0", "sha256": "b" * 64}, "primary_sources": [{"locator": "https://github.com/anthropics/skills", "archive_member": "safe/catalog.json", "pointer": "/entries/0", "capture_sha256": "a" * 64, "subject": "implementation", "prompt": "PRIVATE-PROMPT"}]})
        row = sources._g5_row(record, "asset#/compact/rows.json", False)
        self.assertEqual(row["quality_evidence"]["maintenance"]["fields"]["maintenance"]["pushed_at"], "2026-10-08")
        self.assertEqual(row["quality_evidence"]["releases"]["fields"]["releases"][0]["tag_name"], "v1")
        self.assertEqual(row["quality_evidence"]["tests"]["status"], "UNREPORTED")
        self.assertEqual(row["primary_sources"][0]["capture_sha256"], "a" * 64)
        self.assertEqual(row["source_entry_witness"]["sha256"], "b" * 64)
        for forbidden in ("PRIVATE-PROMPT", "PRIVATE-TASK", '"prompt"', '"task"'):
            self.assertNotIn(forbidden, json.dumps(row))


if __name__ == "__main__":
    unittest.main()
