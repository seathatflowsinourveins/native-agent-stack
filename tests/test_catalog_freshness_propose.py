"""Regression coverage for scripts/freshness_propose.py and the `propose` job it
backs in .github/workflows/catalog-freshness.yml (docs/decisions/2026-09-23-bot-pr-dispatch.md).

`scripts/freshness_propose.py`'s unit tests use only synthetic fixtures (never a
real drift artifact) and confirm the resulting publication passes
`scripts.validate.validate()` end to end, that catalog selection files are never
touched, and that neither `manifests/evidence.json`'s `files[]`/`receipts[]`
order nor `docs/ecosystem/index.html`'s tracked/untracked state is assumed.

The workflow-text tests below are text-level, like
`tests/test_catalog_freshness_pins.py`: they check the `propose` job's trigger
condition, permissions, pinned actions and forbidden-path discipline directly
against the committed YAML bytes, without a YAML dependency.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import freshness_propose as fp
from scripts.validate import validate


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/catalog-freshness.yml"
FORBIDDEN_CATALOG_PREFIXES = (
    "catalogs/sota-convergence/", "catalogs/landscape/", "manifests/stack.json", "layer-verdicts",
)


def _drift_md(rows):
    lines = [
        "# Catalog freshness drift", "",
        "Published manifest: `catalogs/sota-convergence/manifest-20260922.json`",
        "Rebuilt manifest: `manifest-20260923.json`", "",
        "This is a report-only diff; it never writes to the repository or opens an issue.", "",
    ]
    if rows:
        lines += [
            "| id | pin (published) | pin (fresh) | upstream latest (published) | upstream latest (fresh) | behind (published) | behind (fresh) |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        lines += [f"| {row} | 1.0 | 1.1 | v1.0 | v1.1 | True | False |" for row in rows]
    else:
        lines.append("No pin/upstream drift detected for components present in both manifests.")
    return "\n".join(lines) + "\n"


class DriftedComponentIdsTests(unittest.TestCase):
    def test_parses_ids_out_of_the_table_body(self):
        self.assertEqual(fp.drifted_component_ids(_drift_md(["gitleaks", "zizmor"])), ["gitleaks", "zizmor"])

    def test_deduplicates_and_sorts(self):
        self.assertEqual(fp.drifted_component_ids(_drift_md(["zizmor", "gitleaks", "zizmor"])), ["gitleaks", "zizmor"])

    def test_no_drift_sentence_yields_no_ids(self):
        self.assertEqual(fp.drifted_component_ids(_drift_md([])), [])

    def test_ignores_text_outside_the_table(self):
        text = "Some prose with a | pipe | in it.\n" + _drift_md(["gitleaks"])
        self.assertEqual(fp.drifted_component_ids(text), ["gitleaks"])


class SelectReceiptComponentIdsTests(unittest.TestCase):
    def test_prefers_drifted_ids_that_are_known_stack_components(self):
        self.assertEqual(
            fp.select_receipt_component_ids(["gitleaks", "not-a-stack-id"], {"gitleaks", "zizmor"}),
            ["gitleaks"],
        )

    def test_falls_back_to_fixed_ci_tools_when_nothing_drifted_matches(self):
        known = {"gitleaks", "syft", "zizmor", "nautilus-trader", "unrelated"}
        self.assertEqual(
            fp.select_receipt_component_ids(["not-a-stack-id"], known),
            sorted(fp.FALLBACK_COMPONENT_IDS),
        )

    def test_raises_when_neither_drifted_nor_fallback_ids_are_known(self):
        with self.assertRaises(fp.FreshnessProposeError):
            fp.select_receipt_component_ids(["not-a-stack-id"], {"unrelated"})


class BuildReceiptTests(unittest.TestCase):
    def test_claim_states_report_only_no_selection_change_and_pin_bump_rule(self):
        receipt = fp.build_receipt("catalog-freshness-20260923", ["gitleaks"], 1,
                                    "https://example.invalid/run/1", "2026-09-23T00:00:00Z")
        self.assertEqual(receipt["schema_version"], 1)
        self.assertEqual(receipt["kind"], fp.RECEIPT_KIND)
        self.assertIn("report-only", receipt["claim"])
        self.assertIn("was selected, evaluated, or changed", receipt["claim"])
        self.assertIn("pin bump requires its own separately qualified receipt", receipt["claim"])
        self.assertTrue(receipt["limitations"])
        self.assertEqual(receipt["component_ids"], ["gitleaks"])


class ApplyIntegrationTests(unittest.TestCase):
    """End-to-end fixture: build a minimal publication, run apply(), and assert the
    result passes scripts.validate.validate() exactly the way CI's `propose` job does."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "manifests").mkdir()
        (self.root / "evidence" / "artifacts").mkdir(parents=True)
        (self.root / "evidence" / "receipts").mkdir(parents=True)
        (self.root / "catalogs" / "sota-convergence").mkdir(parents=True)
        (self.root / "catalogs" / "landscape").mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)

        self.receipt_id = "catalog-freshness-20260923"
        stack = {
            "schema_version": 1,
            "components": [
                {"id": "gitleaks", "version": "8.30.1", "profile": "core", "commands": ["gitleaks version"],
                 "evidence_ids": [self.receipt_id]},
                {"id": "zizmor", "version": "1.30.1", "profile": "core", "commands": ["zizmor --version"],
                 "evidence_ids": [self.receipt_id]},
            ],
            "profiles": [{"id": "core", "component_ids": ["gitleaks", "zizmor"]}],
            "models": [],
        }
        (self.root / "manifests" / "stack.json").write_text(json.dumps(stack), encoding="utf-8")
        (self.root / "manifests" / "evidence.json").write_text(
            json.dumps({"schema_version": 1, "receipts": [], "files": []}), encoding="utf-8",
        )
        # Sentinel catalog-selection files this module must never touch.
        self.sentinel_paths = {
            "catalogs/sota-convergence/manifest-20260922.json": '{"sentinel": true}',
            "catalogs/landscape/example.json": '{"sentinel": true}',
        }
        for relative, content in self.sentinel_paths.items():
            (self.root / relative).write_text(content, encoding="utf-8")

        self.artifact_dir = self.root / "artifact-in"
        self.artifact_dir.mkdir()
        (self.artifact_dir / "drift.md").write_text(_drift_md(["gitleaks", "zizmor"]), encoding="utf-8")
        (self.artifact_dir / "manifest-20260923.json").write_text(
            json.dumps({"foundation": [], "trading": [], "counts": {}}), encoding="utf-8",
        )

    def test_apply_produces_a_valid_publication(self):
        result = fp.apply(self.root, self.artifact_dir, "https://example.invalid/run/1", "2026-09-23T00:00:00Z")
        self.assertEqual(result["receipt_id"], self.receipt_id)
        self.assertEqual(result["component_ids"], ["gitleaks", "zizmor"])
        self.assertEqual(result["drifted_component_count"], 2)
        self.assertFalse(result["rehashed_explorer"])  # explorer path was never created/tracked

        summary = validate(self.root)
        self.assertEqual(summary["receipts"], 1)

    def test_apply_never_touches_catalog_selection_files(self):
        before = {relative: (self.root / relative).read_text(encoding="utf-8") for relative in self.sentinel_paths}
        fp.apply(self.root, self.artifact_dir, "https://example.invalid/run/1", "2026-09-23T00:00:00Z")
        after = {relative: (self.root / relative).read_text(encoding="utf-8") for relative in self.sentinel_paths}
        self.assertEqual(before, after)
        # manifests/stack.json is read but never written by apply().
        stack_before = json.loads((self.root / "manifests" / "stack.json").read_text(encoding="utf-8"))
        fp.apply(self.root, self.artifact_dir, "https://example.invalid/run/2", "2026-09-23T00:00:00Z")
        stack_after = json.loads((self.root / "manifests" / "stack.json").read_text(encoding="utf-8"))
        self.assertEqual(stack_before, stack_after)

    def test_apply_is_idempotent_on_rerun_for_the_same_date(self):
        fp.apply(self.root, self.artifact_dir, "https://example.invalid/run/1", "2026-09-23T00:00:00Z")
        fp.apply(self.root, self.artifact_dir, "https://example.invalid/run/2", "2026-09-23T00:00:00Z")
        evidence = json.loads((self.root / "manifests" / "evidence.json").read_text(encoding="utf-8"))
        matching_receipts = [r for r in evidence["receipts"] if r["id"] == self.receipt_id]
        self.assertEqual(len(matching_receipts), 1, "rerunning for the same date must upsert, not duplicate")
        # A rerun still leaves a fully valid publication.
        validate(self.root)

    def test_apply_tolerates_files_and_receipts_in_either_order(self):
        """manifests/evidence.json's files[]/receipts[] order is never assumed; pre-seed
        both lists with an unrelated entry positioned after where ours would naturally
        land, so a position-based (rather than id/path-based) lookup would misbehave."""
        evidence_path = self.root / "manifests" / "evidence.json"
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence["files"].append({"path": "evidence/artifacts/unrelated.txt", "sha256": "0" * 64, "bytes": 0})
        evidence["receipts"].append({
            "id": "zzz-unrelated", "kind": "artifact_measurement", "component_ids": ["gitleaks"],
            "claim": "unrelated", "limitations": ["unrelated"], "path": "evidence/receipts/zzz-unrelated.json",
        })
        evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
        result = fp.apply(self.root, self.artifact_dir, "https://example.invalid/run/1", "2026-09-23T00:00:00Z")
        self.assertEqual(result["receipt_id"], self.receipt_id)
        evidence_after = json.loads(evidence_path.read_text(encoding="utf-8"))
        self.assertIn("zzz-unrelated", [r["id"] for r in evidence_after["receipts"]])
        self.assertIn(self.receipt_id, [r["id"] for r in evidence_after["receipts"]])

    def test_apply_raises_on_missing_manifest_in_artifact(self):
        empty_artifact = self.root / "artifact-empty"
        empty_artifact.mkdir()
        (empty_artifact / "drift.md").write_text(_drift_md([]), encoding="utf-8")
        with self.assertRaises(fp.FreshnessProposeError):
            fp.apply(self.root, empty_artifact, "https://example.invalid/run/1", "2026-09-23T00:00:00Z")

    def test_apply_picks_the_newest_manifest_by_name(self):
        (self.artifact_dir / "manifest-20260101.json").write_text(
            json.dumps({"foundation": [], "trading": [], "counts": {}}), encoding="utf-8",
        )
        result = fp.apply(self.root, self.artifact_dir, "https://example.invalid/run/1", "2026-09-23T00:00:00Z")
        self.assertTrue(result["artifact_paths"][1].endswith("manifest-20260923.json"))


class IsGitTrackedTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)

    def test_false_for_a_file_that_does_not_exist(self):
        self.assertFalse(fp.is_git_tracked(self.root, "docs/ecosystem/index.html"))

    def test_false_for_an_untracked_file_on_disk(self):
        (self.root / "docs").mkdir()
        (self.root / "docs" / "index.html").write_text("<html></html>", encoding="utf-8")
        self.assertFalse(fp.is_git_tracked(self.root, "docs/index.html"))

    def test_true_once_staged(self):
        (self.root / "docs").mkdir()
        (self.root / "docs" / "index.html").write_text("<html></html>", encoding="utf-8")
        subprocess.run(["git", "add", "docs/index.html"], cwd=self.root, check=True)
        self.assertTrue(fp.is_git_tracked(self.root, "docs/index.html"))


class CatalogFreshnessWorkflowTextTests(unittest.TestCase):
    """Text-level checks against the committed workflow, mirroring
    tests/test_catalog_freshness_pins.py's approach (no YAML dependency)."""

    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_open_pr_dispatch_input_is_a_boolean_defaulting_false(self):
        match = re.search(
            r"open_pr:\s*\n\s*description:[^\n]*\n\s*type:\s*boolean\s*\n\s*default:\s*false", self.text,
        )
        self.assertIsNotNone(match, "workflow_dispatch.inputs.open_pr must be a boolean defaulting to false")

    def test_freshness_job_exposes_a_drift_output(self):
        self.assertRegex(self.text, r"(?m)^\s+outputs:\s*\n\s+drift:\s*\$\{\{\s*steps\.diff\.outputs\.drift\s*\}\}")

    def test_diff_step_no_longer_hardcodes_a_dated_manifest_filename(self):
        self.assertNotIn("manifest-20260922.json", self.text)

    def test_diff_step_sorts_published_manifests_by_name(self):
        self.assertIn("sorted(Path(\"catalogs/sota-convergence\").glob(\"manifest-*.json\"))", self.text)

    def test_propose_job_condition_matches_the_specified_gate(self):
        self.assertIn("needs.freshness.outputs.drift == 'true'", self.text)
        self.assertIn("inputs.open_pr == true", self.text)
        self.assertIn("vars.CATALOG_FRESHNESS_PROPOSE == 'true'", self.text)
        self.assertIn("github.event_name == 'schedule'", self.text)

    def test_propose_job_permissions_are_scoped_to_exactly_the_three_needed_scopes(self):
        # This is the one job in this workflow allowed to write (docs/decisions/
        # 2026-09-23-bot-pr-dispatch.md): it only ever touches evidence/artifacts/*,
        # evidence/receipts/* and manifests/evidence.json's registration (enforced by
        # ApplyIntegrationTests.test_apply_never_touches_catalog_selection_files above),
        # then opens a human-reviewable PR and dispatches the two downstream check runs.
        match = re.search(r"(?m)^  propose:\n(.*?)(?=^  \w[\w-]*:|\Z)", self.text, re.DOTALL)
        self.assertIsNotNone(match, "propose job not found")
        body = match.group(1)
        permission_match = re.search(r"(?m)^    permissions:\n((?:      [^\n]*\n)+)", body)
        self.assertIsNotNone(permission_match, "propose job needs its own permissions block")
        entries = {}
        for line in permission_match.group(1).splitlines():
            if not line.strip():
                continue
            key, value = line.strip().split(":", 1)
            entries[key.strip()] = value.split("#", 1)[0].strip()
        self.assertEqual(entries, {"contents": "write", "pull-requests": "write", "actions": "write"})

    def test_top_level_permissions_stay_read_only(self):
        top_level = self.text.split("\njobs:\n", 1)[0]
        self.assertIn("permissions:\n  contents: read", top_level)

    def test_propose_job_never_references_forbidden_catalog_paths_for_writing(self):
        match = re.search(r"(?m)^  propose:\n(.*?)(?=^  \w[\w-]*:|\Z)", self.text, re.DOTALL)
        body = match.group(1)
        for forbidden in FORBIDDEN_CATALOG_PREFIXES:
            self.assertNotIn(forbidden, body,
                              f"propose job must not reference {forbidden!r} (owned by the SOTA-convergence lane)")

    def test_propose_job_cites_the_github_token_event_trigger_docs(self):
        match = re.search(r"(?m)^  propose:\n(.*?)(?=^  \w[\w-]*:|\Z)", self.text, re.DOTALL)
        body = match.group(1)
        self.assertIn("https://docs.github.com/en/actions/concepts/security/github_token", body)

    def test_propose_job_never_persists_the_token_to_a_git_credential_store(self):
        match = re.search(r"(?m)^  propose:\n(.*?)(?=^  \w[\w-]*:|\Z)", self.text, re.DOTALL)
        body = match.group(1)
        self.assertIn("persist-credentials: false", body)
        self.assertIn("GIT_CONFIG_COUNT", body)
        self.assertNotIn("credential.helper", body)

    def test_download_artifact_action_is_pinned_by_full_sha(self):
        self.assertRegex(self.text, r"actions/download-artifact@[0-9a-f]{40} # v\d")


if __name__ == "__main__":
    unittest.main()
