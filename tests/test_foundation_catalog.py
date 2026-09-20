"""Reject unsupported adoption claims using small, independent public fixtures."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/validate_foundation.py"
LAYERS = "native-clients instructions-skills workers isolation code-navigation document-retrieval semantic-rag durable-memory web-research token-efficiency quality-evaluation ci-supply-chain scheduling-supervision hosting-services recovery-portability observation-inference".split()
MANIFEST = "catalogs/foundation/manifest.json"
DECISIONS = "catalogs/foundation/decisions.json"
MATRIX = "blueprints/token-native-focus/saturation-audit.json"


class FoundationCatalogTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.manifest = {
            "schema_version": 1, "catalog_id": "foundation", "checked_at": "2026-09-20",
            "scope": "General engineering fixture on one historical host.",
            "limitations": ["No new-host acceptance."],
            "canonical_sources": {"components": "manifests/stack.json", "evidence": "manifests/evidence.json",
                                  "lifecycle": MATRIX, "shared_research_inventory": "catalogs/us-equities/decision-index.json"},
            "decisions_file": DECISIONS,
            "layers": [{"id": layer, "title": layer, "purpose": "Bounded purpose", "selection": "Selected fixture",
                        "activation": "Only on demand", "lifecycle_scope": "One use accepted; recovery unknown",
                        "next_gap": "Exercise recovery on selected host"} for layer in LAYERS],
            "domain_boundary": [{"component_id": "domain", "catalog": "catalogs/us-equities/README.md",
                                 "scope": "Specialist example only; not foundation acceptance"}],
            "top_gaps": [{"id": f"gap-{i}", "priority": i, "status": "open", "scope": "One scoped gap",
                          "next_action": "Run a bounded acceptance", "source_paths": ["guide.md"]} for i in (1, 2, 3)],
            "open_gates": [{"id": f"gap-{i}", "gap_id": f"gap-{i}"} for i in (1, 2, 3)],
        }
        self.decision = {
            "id": "source-retrieval", "capability": "Retrieve exact source", "capability_key": "source-retrieval",
            "checked_at": "2026-09-20", "layer_ids": LAYERS,
            "selection": "default", "review_status": "accepted_within_scope", "activation": "Select the fixture",
            "component_ids": ["tool"], "candidate": None, "evidence_ids": ["native"],
            "evidence_scope": "One source function on the recorded host", "limitations": ["No arbitrary corpus acceptance"],
            "source_paths": ["guide.md"], "next_gap": "Try the selected target corpus",
            "lifecycle": {"source_path": MATRIX, "scope": "Native use only", "unknown": "Recovery unestablished",
                          "stage_refs": [{"component_id": "tool", "stage": "use", "status": "accepted_within_scope"}]},
            "supersedes": [],
        }
        self.decisions = {"schema_version": 1, "checked_at": "2026-09-20", "scope": "Capability-specific fixture",
                          "decisions": [self.decision]}
        self.write("manifests/stack.json", {"components": [{"id": "tool", "version": "1"}, {"id": "domain", "version": "1"}]})
        self.write("manifests/evidence.json", {"receipts": [{"id": "native", "kind": "native_cli_e2e", "path": "receipt.json",
                    "component_ids": ["tool"], "claim": "One useful operation", "limitations": ["One host"]}]})
        self.write(MATRIX, {"components": [{"component_id": "tool", "lifecycle_stages": {
            "use": {"status": "accepted_within_scope", "scope": "Native use only", "evidence_refs": ["receipt.json"]},
            "recovery": {"status": "not_established", "scope": "Not tested", "evidence_refs": []}}}]})
        for path in ("guide.md", "receipt.json", "catalogs/us-equities/decision-index.json", "catalogs/us-equities/README.md"):
            self.write(path, {})

    def write(self, path, value):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value), encoding="utf-8")

    def run_check(self):
        self.write(MANIFEST, self.manifest)
        self.write(DECISIONS, self.decisions)
        result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root), "--json"],
                                text=True, capture_output=True, check=False)
        return result, json.loads(result.stdout) if result.stdout.strip().startswith("{") else {}

    def assert_invalid(self, fragment):
        result, report = self.run_check()
        self.assertEqual(result.returncode, 1, result.stderr or result.stdout)
        self.assertIn(fragment, " ".join(report.get("errors", [])))

    def test_valid_catalog_resolves_historical_claims_without_executing_them(self):
        result, report = self.run_check()
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(report["counts"], {"layers": 16, "decisions": 1, "foundation_components": 1,
                                         "domain_components": 1, "evidence_receipts": 1, "candidates": 0})

    def test_duplicate_decision_ids_fail(self):
        self.decisions["decisions"].append(copy.deepcopy(self.decision))
        self.assert_invalid("duplicate")

    def test_missing_or_unknown_layers_fail(self):
        self.manifest["layers"].pop()
        self.assert_invalid("16 required layers")
        self.setUp()
        self.decision["layer_ids"] = ["imaginary-layer"]
        self.assert_invalid("unknown layer")

    def test_nonexistent_component_and_unrelated_receipt_fail(self):
        self.decision["component_ids"] = ["missing"]
        self.assert_invalid("unknown component")
        self.setUp()
        self.write("manifests/evidence.json", {"receipts": [{"id": "native", "kind": "native_cli_e2e",
                   "path": "receipt.json", "component_ids": ["domain"], "claim": "Different use", "limitations": ["Narrow"]}]})
        self.assert_invalid("unrelated evidence")

    def test_unknown_receipt_and_missing_evidence_file_fail(self):
        self.decision["evidence_ids"] = ["missing"]
        self.assert_invalid("unknown evidence")
        self.setUp()
        (self.root / "receipt.json").unlink()
        self.assert_invalid("file missing")

    def test_missing_scope_and_empty_limitations_fail(self):
        for field, value in (("evidence_scope", ""), ("limitations", []), ("activation", ""), ("next_gap", "")):
            with self.subTest(field=field):
                old = self.decision[field]
                self.decision[field] = value
                self.assert_invalid(field)
                self.decision[field] = old

    def test_paths_cannot_escape_follow_symlinks_or_name_missing_files(self):
        (self.root / "linked.md").symlink_to(self.root / "guide.md")
        for path, message in (("../guide.md", "confined"), ("linked.md", "symlinks"), ("absent.md", "file missing")):
            with self.subTest(path=path):
                self.decision["source_paths"] = [path]
                self.assert_invalid(message)

    def test_unknown_lifecycle_status_or_promotion_of_unknown_stage_fails(self):
        stage = self.decision["lifecycle"]["stage_refs"][0]
        stage["status"] = "fully-working"
        self.assert_invalid("lifecycle status")
        stage.update(stage="recovery", status="accepted_within_scope")
        self.assert_invalid("lifecycle status differs")

    def test_native_acceptance_requires_execution_evidence_not_inventory(self):
        data = json.loads((self.root / "manifests/evidence.json").read_text())
        data["receipts"][0]["kind"] = "historical_inventory"
        self.write("manifests/evidence.json", data)
        self.assert_invalid("execution evidence")

    def test_partial_lifecycle_cannot_be_reclassified_as_accepted_capability(self):
        data = json.loads((self.root / MATRIX).read_text())
        data["components"][0]["lifecycle_stages"]["use"]["status"] = "partial_acceptance"
        self.write(MATRIX, data)
        self.decision["lifecycle"]["stage_refs"][0]["status"] = "partial_acceptance"
        self.assert_invalid("accepted stage")

    def test_pin_and_receipt_copies_are_rejected(self):
        for field, value in (("version", "2.0"), ("source_pin", "a" * 40), ("receipts", [{"claim": "Everything passed"}])):
            with self.subTest(field=field):
                self.decision[field] = value
                self.assert_invalid("unknown fields")
                del self.decision[field]

    def test_candidate_cannot_claim_adopted_components_or_native_acceptance(self):
        self.decision.update(selection="candidate", review_status="source_review", component_ids=[], evidence_ids=[],
                             candidate={"id": "new-tool", "repository": "https://github.com/example/new-tool"})
        self.decision["lifecycle"]["stage_refs"] = []
        result, _ = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.decision["review_status"] = "accepted_within_scope"
        self.assert_invalid("candidate")

    def test_domain_components_cannot_be_promoted_by_catalog_placement(self):
        self.manifest["domain_boundary"][0]["component_id"] = "tool"
        self.assert_invalid("domain boundary")

    def test_open_gates_must_resolve_every_unfinished_gap(self):
        self.manifest["open_gates"][0]["gap_id"] = "unknown"
        self.assert_invalid("unknown gap")
        self.manifest["open_gates"].pop(0)
        self.assert_invalid("unfinished gaps")

    def test_scoped_accepted_gap_stays_recorded_without_an_open_gate(self):
        self.manifest["top_gaps"][0]["status"] = "accepted_within_scope"
        closed_gate = self.manifest["open_gates"].pop(0)
        result, report = self.run_check()
        self.assertEqual(result.returncode, 0, result.stderr or str(report))
        self.manifest["open_gates"].append(closed_gate)
        self.assert_invalid("unfinished gaps")

    def test_supersession_requires_same_capability_and_earlier_date(self):
        old = copy.deepcopy(self.decision)
        old.update(id="older", checked_at="2026-09-19")
        self.decisions["decisions"].append(old)
        self.decision["supersedes"] = [{"decision_id": "older", "scope": "Same fixture", "reason": "Later scoped result"}]
        result, _ = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout)
        old["capability_key"] = "another-capability"
        self.assert_invalid("same capability")
        old["capability_key"] = self.decision["capability_key"]
        old["checked_at"] = "2026-09-20"
        self.assert_invalid("earlier")
        old["checked_at"] = "2026-09-19"
        self.decision["supersedes"][0]["decision_id"] = "absent"
        self.assert_invalid("unknown superseded")

    def test_duplicate_json_keys_fail_with_a_machine_readable_error(self):
        (self.root / "manifests/stack.json").write_text('{"components":[],"components":[]}')
        self.assert_invalid("duplicate key")

    def test_checked_in_catalog_passes(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(ROOT), "--json"],
                                text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
