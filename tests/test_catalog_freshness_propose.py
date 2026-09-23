"""Regression coverage for scripts/freshness_propose.py and the `propose` job it
backs in .github/workflows/catalog-freshness.yml (docs/decisions/2026-09-23-bot-pr-dispatch.md).

`scripts/freshness_propose.py`'s unit tests use only synthetic fixtures (never a
real drift artifact) and confirm the resulting publication passes
`scripts.validate.validate()` end to end, that catalog selection files are never
touched, and that neither `manifests/evidence.json`'s `files[]`/`receipts[]`
order nor `docs/ecosystem/index.html`'s tracked/untracked state is assumed.

`RebuildExplorerSubprocessTests` runs the module as a real subprocess (not an
in-process call) against a throwaway git-tracked copy of this repository, to
reproduce and guard the fix for the H1 finding from the 2026-09-23 fix round
(docs/decisions/2026-09-23-bot-pr-dispatch.md): scripts/build_ecosystem.py's own
stdout must never land inside main()'s single-JSON-document stdout contract.

The workflow-text tests below are text-level, like
`tests/test_catalog_freshness_pins.py`: they check the `propose` job's trigger
condition, permissions, pinned actions and forbidden-path discipline directly
against the committed YAML bytes, without a YAML dependency.
"""

from __future__ import annotations

import json
import re
import shutil
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
EXPECTED_PROPOSE_IF = (
    "github.ref == 'refs/heads/main' && needs.freshness.outputs.drift == 'true' && "
    "(inputs.max_repos || 0) == 0 && needs.freshness.outputs.upstream_errors == '0' && "
    "(inputs.open_pr == true || (github.event_name == 'schedule' && vars.CATALOG_FRESHNESS_PROPOSE == 'true'))"
)


def _drift_md(rows, unfetched=()):
    """Build drift.md text using the *same* header/separator/escaping the
    production code uses (fp.DRIFT_TABLE_HEADER/SEPARATOR/md_cell), so a
    fixture can never silently drift out of sync with what
    render_drift_markdown() actually writes. `rows` is a list of component
    ids; each gets a synthetic (pin, latest, behind) drift row.
    """
    lines = [
        "# Catalog freshness drift", "",
        "Published manifest: `catalogs/sota-convergence/manifest-20260922.json`",
        "Rebuilt manifest: `manifest-20260923.json`", "",
        "This diff is report-only; it changes no catalog selection.", "",
    ]
    if rows:
        lines += [fp.DRIFT_TABLE_HEADER, fp.DRIFT_TABLE_SEPARATOR]
        for row_id in rows:
            values = (row_id, "1.0", "1.1", "v1.0", "v1.1", True, False)
            lines.append("| " + " | ".join(fp.md_cell(v) for v in values) + " |")
    else:
        lines.append("No pin/upstream drift detected for components present in both manifests.")
    if unfetched:
        lines += [
            "", f"{len(unfetched)} component(s) had no fetched upstream 'latest' this run "
                "(unbounded max_repos or a fetch error) and are excluded from the drift count above:",
            "", ", ".join(fp.md_cell(component_id) for component_id in unfetched),
        ]
    return "\n".join(lines) + "\n"


class MdCellTests(unittest.TestCase):
    def test_wraps_value_in_backtick_inline_code(self):
        self.assertEqual(fp.md_cell("v1.2.3"), "`v1.2.3`")

    def test_escapes_pipe_so_it_cannot_end_the_cell_early(self):
        self.assertEqual(fp.md_cell("a|b"), "`a\\|b`")

    def test_neutralizes_a_literal_backtick(self):
        self.assertNotIn("``", fp.md_cell("a`b"))

    def test_none_renders_as_a_literal_placeholder(self):
        self.assertEqual(fp.md_cell(None), "`(none)`")


class ComputeDriftTests(unittest.TestCase):
    def _row(self, pin, latest, behind):
        return {"pin": pin, "upstream": {"latest": latest}, "pin_behind_upstream": behind}

    def test_pin_change_is_drift(self):
        published = {"gitleaks": self._row("8.30.0", "v8.30.0", False)}
        rebuilt = {"gitleaks": self._row("8.30.1", "v8.30.0", False)}
        drifted, unfetched = fp.compute_drift(published, rebuilt)
        self.assertEqual([row[0] for row in drifted], ["gitleaks"])
        self.assertEqual(unfetched, [])

    def test_no_change_is_not_drift(self):
        row = self._row("8.30.1", "v8.30.1", False)
        drifted, unfetched = fp.compute_drift({"gitleaks": row}, {"gitleaks": dict(row)})
        self.assertEqual(drifted, [])
        self.assertEqual(unfetched, [])

    def test_unfetched_upstream_latest_is_excluded_from_drift(self):
        """A rebuilt row with upstream.latest=None (github_freshness.py never fetched
        it this run -- a bounded --max-repos run or an API error) must not be reported
        as drift just because it differs from a real prior value."""
        published = {"gitleaks": self._row("8.30.0", "v8.30.0", False)}
        rebuilt = {"gitleaks": self._row("8.30.0", None, False)}
        drifted, unfetched = fp.compute_drift(published, rebuilt)
        self.assertEqual(drifted, [])
        self.assertEqual(unfetched, ["gitleaks"])

    def test_component_absent_from_published_is_ignored(self):
        drifted, unfetched = fp.compute_drift({}, {"new-thing": self._row("1.0", "v1.0", False)})
        self.assertEqual(drifted, [])
        self.assertEqual(unfetched, [])


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

    def test_ignores_the_unfetched_section(self):
        text = _drift_md(["gitleaks"], unfetched=["syft"])
        self.assertEqual(fp.drifted_component_ids(text), ["gitleaks"])


class BuildDriftReportTests(unittest.TestCase):
    """build_drift_report() is what both catalog-freshness.yml's diff step and
    the tests above ultimately rely on; exercise it directly against real files
    on disk so the header/separator/escaping used to write drift.md and the
    header/separator used to read it back can never diverge (T3)."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work_dir = Path(self.temporary.name) / "work"
        self.work_dir.mkdir()
        self.published_dir = Path(self.temporary.name) / "catalogs" / "sota-convergence"
        self.published_dir.mkdir(parents=True)
        self._original_cwd = Path.cwd()
        import os
        os.chdir(self.temporary.name)
        self.addCleanup(os.chdir, self._original_cwd)

    def _write_manifest(self, path, rows):
        path.write_text(json.dumps({
            "foundation": [{"components": [
                {"id": component_id, "pin": pin, "upstream": {"latest": latest}, "pin_behind_upstream": behind}
                for component_id, pin, latest, behind in rows
            ]}],
            "trading": [], "counts": {"foundation_layers": 1},
        }), encoding="utf-8")

    def test_drift_true_when_a_component_actually_changed(self):
        self._write_manifest(self.published_dir / "manifest-20260922.json",
                              [("gitleaks", "8.30.0", "v8.30.0", False)])
        self._write_manifest(self.work_dir / "manifest-20260923.json",
                              [("gitleaks", "8.30.1", "v8.30.1", False)])
        result = fp.build_drift_report(self.work_dir)
        self.assertEqual(result["drifted"], ["gitleaks"])
        self.assertEqual((self.work_dir / "drift-status.txt").read_text().strip(), "true")
        drift_text = (self.work_dir / "drift.md").read_text()
        self.assertIn(fp.DRIFT_TABLE_HEADER, drift_text)
        self.assertIn("report-only", drift_text)
        self.assertIn("changes no catalog selection", drift_text)
        self.assertNotIn("never writes to the repository or opens an issue", drift_text)

    def test_drift_false_and_unfetched_reported_separately(self):
        self._write_manifest(self.published_dir / "manifest-20260922.json",
                              [("gitleaks", "8.30.0", "v8.30.0", False)])
        self._write_manifest(self.work_dir / "manifest-20260923.json",
                              [("gitleaks", "8.30.0", None, False)])
        result = fp.build_drift_report(self.work_dir)
        self.assertEqual(result["drifted"], [])
        self.assertEqual(result["unfetched"], ["gitleaks"])
        self.assertEqual((self.work_dir / "drift-status.txt").read_text().strip(), "false")

    def test_upstream_error_count_defaults_to_zero_when_file_absent(self):
        self._write_manifest(self.published_dir / "manifest-20260922.json", [])
        self._write_manifest(self.work_dir / "manifest-20260923.json", [])
        fp.build_drift_report(self.work_dir)
        self.assertEqual((self.work_dir / "upstream-errors.txt").read_text().strip(), "0")

    def test_upstream_error_count_reads_the_freshness_document(self):
        self._write_manifest(self.published_dir / "manifest-20260922.json", [])
        self._write_manifest(self.work_dir / "manifest-20260923.json", [])
        (self.work_dir / "github-freshness.json").write_text(json.dumps({"errors": 3}), encoding="utf-8")
        fp.build_drift_report(self.work_dir)
        self.assertEqual((self.work_dir / "upstream-errors.txt").read_text().strip(), "3")


class SelectReceiptComponentIdsTests(unittest.TestCase):
    def test_prefers_drifted_ids_that_are_known_stack_components(self):
        self.assertEqual(
            fp.select_receipt_component_ids(["gitleaks", "not-a-stack-id"], {"gitleaks", "zizmor"}),
            ["gitleaks"],
        )

    def test_raises_when_no_drifted_id_is_a_known_stack_component(self):
        """No fallback to an unrelated fixed component set (L2): a receipt whose
        component_ids do not describe what actually drifted must never be produced."""
        with self.assertRaises(fp.FreshnessProposeError):
            fp.select_receipt_component_ids(["not-a-stack-id"], {"gitleaks", "zizmor", "syft", "nautilus-trader"})

    def test_raises_when_drifted_ids_are_empty(self):
        with self.assertRaises(fp.FreshnessProposeError):
            fp.select_receipt_component_ids([], {"gitleaks"})


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
        self.assertNotIn("fallback", " ".join(receipt["limitations"]).lower())
        self.assertEqual(receipt["component_ids"], ["gitleaks"])


class RefuseIfSymlinkTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_raises_for_an_existing_symlink(self):
        target = self.root / "real.txt"
        target.write_text("sentinel", encoding="utf-8")
        link = self.root / "link.txt"
        link.symlink_to(target)
        with self.assertRaises(fp.FreshnessProposeError):
            fp.refuse_if_symlink(link)
        self.assertEqual(target.read_text(encoding="utf-8"), "sentinel")

    def test_does_not_raise_for_a_plain_file_or_missing_path(self):
        plain = self.root / "plain.txt"
        plain.write_text("x", encoding="utf-8")
        fp.refuse_if_symlink(plain)
        fp.refuse_if_symlink(self.root / "does-not-exist.txt")


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
        validate(self.root)

    def test_apply_tolerates_files_and_receipts_in_either_order(self):
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

    def test_apply_refuses_a_symlinked_receipt_destination(self):
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        sentinel = outside / "sentinel.json"
        sentinel.write_text('{"planted": true}', encoding="utf-8")
        link = self.root / "evidence" / "receipts" / f"{self.receipt_id}.json"
        link.symlink_to(sentinel)
        with self.assertRaises(fp.FreshnessProposeError):
            fp.apply(self.root, self.artifact_dir, "https://example.invalid/run/1", "2026-09-23T00:00:00Z")
        self.assertEqual(sentinel.read_text(encoding="utf-8"), '{"planted": true}')

    def test_apply_raises_when_drift_does_not_match_any_stack_component(self):
        (self.artifact_dir / "drift.md").write_text(_drift_md(["totally-unrelated-repo"]), encoding="utf-8")
        with self.assertRaises(fp.FreshnessProposeError):
            fp.apply(self.root, self.artifact_dir, "https://example.invalid/run/1", "2026-09-23T00:00:00Z")


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


def _init_scratch_git(path: Path) -> None:
    git_env = ["-c", "user.email=scratch@example.invalid", "-c", "user.name=scratch"]
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", *git_env, "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", *git_env, "commit", "-q", "-m", "scratch snapshot"], cwd=path, check=True)


def _run_propose_cli(scratch: Path, artifact_dir: Path, checked_at="2026-09-23T00:00:00Z"):
    return subprocess.run(
        ["python3", "scripts/freshness_propose.py", "--artifact-dir", str(artifact_dir),
         "--run-url", "https://example.invalid/run/1", "--checked-at-utc", checked_at],
        cwd=scratch, capture_output=True, text=True, timeout=180,
    )


def _make_artifact(scratch: Path, name: str, rows=("gitleaks",)) -> Path:
    artifact_dir = scratch / name
    artifact_dir.mkdir(exist_ok=True)
    (artifact_dir / "drift.md").write_text(_drift_md(list(rows)), encoding="utf-8")
    (artifact_dir / "manifest-20260923.json").write_text(
        json.dumps({"foundation": [], "trading": [], "counts": {}}), encoding="utf-8",
    )
    return artifact_dir


@unittest.skipUnless(shutil.which("git"), "git is required to build the scratch checkout")
class RebuildExplorerSubprocessTests(unittest.TestCase):
    """Real subprocess invocations of scripts/freshness_propose.py's CLI against a
    throwaway, git-tracked copy of this repository, guarding the H1 fix
    (build_ecosystem.py's own stdout leaking into main()'s single-JSON-document
    stdout, making `json.load` fail with "Extra data").

    docs/ecosystem/index.html is untracked and .gitignore'd on main
    (docs/decisions/2026-09-23-generated-explorer-sorted-manifest.md), so a
    plain copy of this repository has it absent -- that is the default,
    normal-case fixture below. `TrackedExplorerSubprocessTests` (a separate
    class) additionally builds and tracks the file inside its own scratch
    copy, to keep exercising rebuild_explorer()'s branch even though it is
    currently unreachable from a checkout of main.

    Uses a plain filesystem copy plus a fresh, single-commit git history
    (fast: well under a second), which is sufficient for is_git_tracked() and
    scripts/validate.py, but is NOT real project history -- host_receipts.py
    validate (which resolves existing receipts' pinned commits) is
    intentionally not run against either scratch copy.
    """

    @classmethod
    def setUpClass(cls):
        cls.scratch = Path(tempfile.mkdtemp(prefix="freshness-default-scratch-"))
        shutil.copytree(
            ROOT, cls.scratch, dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".pytest_cache"),
        )
        _init_scratch_git(cls.scratch)
        assert not fp.is_git_tracked(cls.scratch, fp.EXPLORER_PATH), \
            "fixture setup assumption failed: docs/ecosystem/index.html must NOT be tracked by default"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.scratch, ignore_errors=True)

    def test_main_stdout_is_exactly_one_json_document(self):
        artifact_dir = _make_artifact(self.scratch, "artifact-h1")
        result = _run_propose_cli(self.scratch, artifact_dir, checked_at="2026-09-23T01:00:00Z")
        self.assertEqual(result.returncode, 0, result.stderr[-3000:])
        parsed = json.loads(result.stdout)  # raises json.JSONDecodeError("Extra data", ...) if H1 regresses
        self.assertFalse(parsed["rehashed_explorer"])  # the default, untracked-explorer path
        self.assertEqual(parsed["component_ids"], ["gitleaks"])

    def test_general_publication_validator_passes_after_the_run(self):
        artifact_dir = _make_artifact(self.scratch, "artifact-validate")
        result = _run_propose_cli(self.scratch, artifact_dir, checked_at="2026-09-23T02:00:00Z")
        self.assertEqual(result.returncode, 0, result.stderr[-3000:])
        checked = subprocess.run(
            ["python3", "scripts/validate.py"], cwd=self.scratch, capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)


@unittest.skipUnless(shutil.which("git"), "git is required to build the scratch checkout")
class TrackedExplorerSubprocessTests(unittest.TestCase):
    """The non-default edge case, kept for forward compatibility: if
    docs/ecosystem/index.html were ever tracked again, rebuild_explorer()'s
    --write/register/--check loop must still work and must still keep
    main()'s stdout to exactly one JSON document (H1). This path is dead
    code on the current main (the file is .gitignore'd there), which is why
    it is a separate, explicitly-labeled class rather than the default
    fixture above.
    """

    @classmethod
    def setUpClass(cls):
        cls.scratch = Path(tempfile.mkdtemp(prefix="freshness-tracked-scratch-"))
        shutil.copytree(
            ROOT, cls.scratch, dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".pytest_cache"),
        )
        built = subprocess.run(
            ["python3", "scripts/build_ecosystem.py", "--write"],
            cwd=cls.scratch, capture_output=True, text=True, timeout=120,
        )
        assert built.returncode == 0, f"fixture setup could not build the explorer: {built.stdout + built.stderr}"
        # .gitignore (copied along with everything else) excludes this file on main
        # (docs/decisions/2026-09-23-generated-explorer-sorted-manifest.md); force-add
        # it here specifically, to simulate the "if it were tracked again" case this
        # class exists to keep exercising.
        git_env = ["-c", "user.email=scratch@example.invalid", "-c", "user.name=scratch"]
        subprocess.run(["git", "init", "-q"], cwd=cls.scratch, check=True)
        subprocess.run(["git", *git_env, "add", "-A"], cwd=cls.scratch, check=True)
        subprocess.run(["git", *git_env, "add", "-f", str(fp.EXPLORER_PATH)], cwd=cls.scratch, check=True)
        subprocess.run(["git", *git_env, "commit", "-q", "-m", "scratch snapshot"], cwd=cls.scratch, check=True)
        assert fp.is_git_tracked(cls.scratch, fp.EXPLORER_PATH), \
            "fixture setup assumption failed: docs/ecosystem/index.html must be tracked in this scratch copy"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.scratch, ignore_errors=True)

    def test_main_stdout_is_exactly_one_json_document_with_tracked_explorer(self):
        artifact_dir = _make_artifact(self.scratch, "artifact-h1-tracked")
        result = _run_propose_cli(self.scratch, artifact_dir, checked_at="2026-09-23T03:00:00Z")
        self.assertEqual(result.returncode, 0, result.stderr[-3000:])
        parsed = json.loads(result.stdout)  # raises json.JSONDecodeError("Extra data", ...) if H1 regresses
        self.assertTrue(parsed["rehashed_explorer"])
        self.assertEqual(parsed["component_ids"], ["gitleaks"])

    def test_explorer_check_passes_after_the_run(self):
        artifact_dir = _make_artifact(self.scratch, "artifact-check-tracked")
        result = _run_propose_cli(self.scratch, artifact_dir, checked_at="2026-09-23T04:00:00Z")
        self.assertEqual(result.returncode, 0, result.stderr[-3000:])
        check = subprocess.run(
            ["python3", "scripts/build_ecosystem.py", "--check"],
            cwd=self.scratch, capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)


class CatalogFreshnessWorkflowTextTests(unittest.TestCase):
    """Text-level checks against the committed workflow, mirroring
    tests/test_catalog_freshness_pins.py's approach (no YAML dependency)."""

    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def _job_body(self, job_id: str) -> str:
        match = re.search(rf"(?m)^  {re.escape(job_id)}:\n(.*?)(?=^  \w[\w-]*:|\Z)", self.text, re.DOTALL)
        self.assertIsNotNone(match, f"{job_id} job not found")
        return match.group(1)

    def test_open_pr_dispatch_input_is_a_boolean_defaulting_false(self):
        match = re.search(
            r"open_pr:\s*\n\s*description:[^\n]*\n\s*type:\s*boolean\s*\n\s*default:\s*false", self.text,
        )
        self.assertIsNotNone(match, "workflow_dispatch.inputs.open_pr must be a boolean defaulting to false")

    def test_freshness_job_exposes_drift_and_upstream_errors_outputs(self):
        self.assertRegex(self.text, r"(?m)^\s+outputs:\s*\n\s+drift:\s*\$\{\{\s*steps\.diff\.outputs\.drift\s*\}\}")
        self.assertRegex(self.text, r"upstream_errors:\s*\$\{\{\s*steps\.diff\.outputs\.upstream_errors\s*\}\}")

    def test_diff_step_no_longer_hardcodes_a_dated_manifest_filename(self):
        self.assertNotIn("manifest-20260922.json", self.text)

    def test_diff_step_delegates_to_the_shared_module_instead_of_reimplementing_the_diff(self):
        body = self._job_body("freshness")
        self.assertIn("from scripts.freshness_propose import build_drift_report", body)
        # T3: the header text must not also be hand-duplicated in the YAML.
        self.assertNotIn("upstream latest (published)", body)

    def test_single_concurrency_group_without_event_name_and_no_cancel(self):
        match = re.search(r"(?m)^concurrency:\n((?:  [^\n]*\n)+)", self.text)
        self.assertIsNotNone(match)
        block = match.group(1)
        self.assertIn("group: ${{ github.workflow }}", block)
        self.assertNotIn("github.event_name", block)
        self.assertIn("cancel-in-progress: false", block)

    def test_propose_job_condition_matches_the_full_normalized_expression(self):
        match = re.search(r"(?m)^  propose:\n(?:.*?\n)*?    if:\s*>-\n((?:      .*\n)+)", self.text)
        self.assertIsNotNone(match, "propose job's if: block not found")
        normalized = " ".join(line.strip() for line in match.group(1).splitlines() if line.strip())
        self.assertEqual(normalized, EXPECTED_PROPOSE_IF)

    def test_propose_job_permissions_are_scoped_to_exactly_contents_and_pull_requests(self):
        # This is the one job in this workflow allowed to write (docs/decisions/
        # 2026-09-23-bot-pr-dispatch.md): it only ever touches evidence/artifacts/*,
        # evidence/receipts/* and manifests/evidence.json's registration (enforced by
        # ApplyIntegrationTests.test_apply_never_touches_catalog_selection_files above),
        # then opens a human-reviewable PR. It no longer dispatches other workflows
        # (removed per the 2026-09-23 fix round), so it needs no `actions: write`.
        body = self._job_body("propose")
        permission_match = re.search(r"(?m)^    permissions:\n((?:      [^\n]*\n)+)", body)
        self.assertIsNotNone(permission_match, "propose job needs its own permissions block")
        entries = {}
        for line in permission_match.group(1).splitlines():
            if not line.strip():
                continue
            key, value = line.strip().split(":", 1)
            entries[key.strip()] = value.split("#", 1)[0].strip()
        self.assertEqual(entries, {"contents": "write", "pull-requests": "write"})
        self.assertNotIn("actions: write", body)

    def test_top_level_permissions_stay_read_only(self):
        top_level = self.text.split("\njobs:\n", 1)[0]
        self.assertIn("permissions:\n  contents: read", top_level)

    def test_propose_job_never_references_forbidden_catalog_paths_for_writing(self):
        body = self._job_body("propose")
        for forbidden in FORBIDDEN_CATALOG_PREFIXES:
            self.assertNotIn(forbidden, body,
                              f"propose job must not reference {forbidden!r} (owned by the SOTA-convergence lane)")

    def test_propose_job_does_not_dispatch_other_workflows(self):
        # Removed per the Codex cross-family review (P1): a workflow_dispatch run's
        # checks do not satisfy a required status check on this PR at all, so
        # `gh workflow run` was a green-looking but not-actually-required substitute.
        # (The prose explaining this removal is allowed to *mention* the phrase in a
        # comment; only an actual, uncommented invocation is checked for here.)
        body = self._job_body("propose")
        invocations = [
            line for line in body.splitlines()
            if "gh workflow run" in line and not line.strip().startswith("#")
        ]
        self.assertEqual(invocations, [])
        self.assertIn("approval-required", body)
        self.assertIn("https://docs.github.com/en/actions/concepts/security/github_token", body)

    def test_propose_job_uses_force_with_lease_not_plain_force(self):
        body = self._job_body("propose")
        self.assertIn("--force-with-lease=", body)
        self.assertNotIn("push --force ", body)

    def test_propose_job_masks_the_basic_auth_header_before_use(self):
        body = self._job_body("propose")
        self.assertIn("::add-mask::$basic_auth", body)

    def test_propose_job_never_persists_the_token_to_a_git_credential_store(self):
        body = self._job_body("propose")
        self.assertIn("persist-credentials: false", body)
        self.assertIn("GIT_CONFIG_COUNT", body)
        self.assertNotIn("credential.helper", body)

    def test_propose_checkout_uses_full_history(self):
        body = self._job_body("propose")
        self.assertIn("fetch-depth: 0", body)

    def test_download_artifact_action_is_pinned_by_full_sha(self):
        self.assertRegex(self.text, r"actions/download-artifact@[0-9a-f]{40} # v\d")


if __name__ == "__main__":
    unittest.main()
