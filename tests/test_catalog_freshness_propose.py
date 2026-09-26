"""Regression coverage for scripts/freshness_propose.py and the `propose` job it
backs in .github/workflows/catalog-freshness.yml (docs/decisions/2026-09-23-bot-pr-dispatch.md).

`scripts/freshness_propose.py`'s unit tests use only synthetic fixtures (never a
real drift artifact) and confirm the resulting publication passes
`scripts.validate.validate()` end to end, that catalog selection files are never
touched, and that neither `manifests/evidence.json`'s `files[]`/`receipts[]`
order nor `docs/ecosystem/index.html`'s tracked/untracked state is assumed.

`RebuildExplorerSubprocessTests` and `TrackedExplorerSubprocessTests` run the
module as a real subprocess (not an in-process call) against a throwaway
git-initialized copy of this repository, to reproduce and guard the fix for
the H1 finding from the 2026-09-23 fix round
(docs/decisions/2026-09-23-bot-pr-dispatch.md): scripts/build_ecosystem.py's
own stdout must never land inside main()'s single-JSON-document stdout
contract. The former uses the plain, untracked-explorer copy that matches
main's real state since #96 (docs/decisions/2026-09-23-generated-explorer-
sorted-manifest.md); the latter additionally force-tracks a locally built
explorer to keep exercising rebuild_explorer()'s branch even though it is
presently unreachable from a checkout of main.

The workflow-text tests below are text-level, like
`tests/test_catalog_freshness_pins.py`: they check the `propose` job's trigger
condition, permissions, pinned actions and forbidden-path discipline directly
against the committed YAML bytes, without a YAML dependency.
"""

from __future__ import annotations

import json
import os
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
    "needs.freshness.outputs.partial_errors == '0' && "
    "(inputs.open_pr == true || (github.event_name == 'schedule' && vars.CATALOG_FRESHNESS_PROPOSE == 'true'))"
)
EXPECTED_PROPOSE_CONCURRENCY_GROUP = (
    "${{ github.workflow }}-propose-${{ inputs.open_pr == true && 'manual' || 'scheduled' }}"
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
    """Regression coverage for the 2026-09-23 second fix round (N1/N2): a pin
    change must never be hidden just because upstream.latest is None, and a
    row is "unfetched" only when it genuinely lacks reliable data -- not
    merely whenever it has no release/tag."""

    def _row(self, pin, latest, behind=False, pushed_at="2026-09-01",
             repository="https://github.com/example/example"):
        return {"pin": pin, "repository": repository,
                "upstream": {"latest": latest, "pushed_at": pushed_at}, "pin_behind_upstream": behind}

    def test_pin_change_is_drift(self):
        published = {"gitleaks": self._row("8.30.0", "v8.30.0")}
        rebuilt = {"gitleaks": self._row("8.30.1", "v8.30.0")}
        drifted, unfetched, no_release = fp.compute_drift(published, rebuilt)
        self.assertEqual([row[0] for row in drifted], ["gitleaks"])
        self.assertEqual(unfetched, [])
        self.assertEqual(no_release, [])

    def test_no_change_is_not_drift(self):
        row = self._row("8.30.1", "v8.30.1")
        drifted, unfetched, no_release = fp.compute_drift({"gitleaks": row}, {"gitleaks": dict(row)})
        self.assertEqual(drifted, [])
        self.assertEqual(unfetched, [])
        self.assertEqual(no_release, [])

    def test_component_absent_from_published_is_ignored(self):
        drifted, unfetched, no_release = fp.compute_drift({}, {"new-thing": self._row("1.0", "v1.0")})
        self.assertEqual(drifted, [])
        self.assertEqual(unfetched, [])
        self.assertEqual(no_release, [])

    def test_no_fetch_evidence_is_unfetched_not_drift(self):
        """pushed_at=None (github_freshness.py never fetched it this run -- a bounded
        --max-repos run or a full fetch failure) must not be reported as drift just
        because it differs from a real prior value."""
        published = {"gitleaks": self._row("8.30.0", "v8.30.0")}
        rebuilt = {"gitleaks": self._row("8.30.0", None, pushed_at=None)}
        drifted, unfetched, no_release = fp.compute_drift(published, rebuilt)
        self.assertEqual(drifted, [])
        self.assertEqual(unfetched, ["gitleaks"])
        self.assertEqual(no_release, [])

    def test_n1_pin_change_is_not_hidden_when_latest_is_none_on_both_sides(self):
        """Exact N1 reproduction (Opus, reproduced by Codex): skills-ref has no GitHub
        releases or tags at all (upstream.latest is None on both sides) but does have
        real fetch data (upstream.pushed_at set) -- catalogs/sota-convergence/
        manifest-20260922.json already has 7 such rows (tavily-cli, skills-ref,
        poppler, ...). A pin bump on one of these must still show as drift; the prior
        implementation skipped straight to "unfetched" whenever latest was None,
        without ever comparing pin, and hid this exact case.
        """
        published = {"skills-ref": self._row("0.1.0", None, pushed_at="2026-08-09")}
        rebuilt = {"skills-ref": self._row("0.1.1", None, pushed_at="2026-08-09")}
        drifted, unfetched, no_release = fp.compute_drift(published, rebuilt)
        self.assertEqual([row[0] for row in drifted], ["skills-ref"])
        self.assertEqual(drifted[0][1:3], ("0.1.0", "0.1.1"))
        self.assertEqual(unfetched, [])
        self.assertEqual(no_release, [])

    def test_codex_original_repro_pin_change_without_fetch_evidence_is_still_drift(self):
        """Codex verification of 7a483f7: the ORIGINAL skills-ref 0.1.0 -> 0.1.1 repro
        has no pushed_at. The pin comes from the local catalogs, so the change must be
        reported as drift even though the upstream fields are unreliable; the row is
        also listed as unfetched and its fresh upstream fields are nulled."""
        published = {"skills-ref": self._row("0.1.0", None, pushed_at=None)}
        rebuilt = {"skills-ref": self._row("0.1.1", None, pushed_at=None)}
        drifted, unfetched, no_release = fp.compute_drift(published, rebuilt)
        self.assertEqual([row[0] for row in drifted], ["skills-ref"])
        self.assertEqual(drifted[0][1:3], ("0.1.0", "0.1.1"))
        self.assertIsNone(drifted[0][4])
        self.assertEqual(unfetched, ["skills-ref"])
        self.assertEqual(no_release, [])

    def test_fetched_with_no_release_and_no_change_is_its_own_category(self):
        """A component reliably fetched this run (pushed_at set, no recorded fetch
        problem) but with no GitHub release or tag on either side, and no pin change,
        is neither drift nor "unfetched" -- it was genuinely, successfully observed."""
        published = {"tavily-cli": self._row("1.0.0", None, pushed_at="2026-09-21")}
        rebuilt = {"tavily-cli": self._row("1.0.0", None, pushed_at="2026-09-21")}
        drifted, unfetched, no_release = fp.compute_drift(published, rebuilt)
        self.assertEqual(drifted, [])
        self.assertEqual(unfetched, [])
        self.assertEqual(no_release, ["tavily-cli"])

    def test_n2_partial_error_with_tag_fallback_is_excluded_from_drift(self):
        """Exact N2 reproduction (Opus finding, reproduced by Codex): a 503 on the
        releases endpoint, worked around by a successful fallback to the tags
        endpoint, still populates upstream.latest with a real-looking value --
        github_freshness.py records this as a "partial_errors" entry, not a full
        "error". That value must not be trusted as clean drift-comparison data just
        because it is not None.
        """
        raw_repositories = {
            "https://github.com/example/flaky": {
                "slug": "example/flaky",
                "latest_tag": "v1.2.0",
                "partial_errors": {"releases": "503 Service Unavailable"},
            },
        }
        published = {"flaky": self._row("1.1.0", "v1.1.0", pushed_at="2026-09-01",
                                         repository="https://github.com/example/flaky")}
        rebuilt = {"flaky": self._row("1.1.0", "v1.2.0", pushed_at="2026-09-20",
                                       repository="https://github.com/example/flaky")}
        drifted, unfetched, no_release = fp.compute_drift(published, rebuilt, raw_repositories)
        self.assertEqual(drifted, [])
        self.assertEqual(unfetched, ["flaky"])
        self.assertEqual(no_release, [])

    def test_full_error_record_is_unfetched_even_with_pushed_at_from_a_prior_run(self):
        """A raw record with a top-level "error" (the repos/{slug} call itself
        failed) must be treated as unfetched even if a retained pushed_at value from
        an earlier successful run is still present in the rebuilt row."""
        raw_repositories = {"https://github.com/example/down": {"slug": "example/down", "error": "404"}}
        published = {"down": self._row("1.0.0", "v1.0.0", pushed_at="2026-08-01",
                                        repository="https://github.com/example/down")}
        rebuilt = {"down": self._row("1.0.0", "v1.0.0", pushed_at="2026-08-01",
                                      repository="https://github.com/example/down")}
        drifted, unfetched, no_release = fp.compute_drift(published, rebuilt, raw_repositories)
        self.assertEqual(drifted, [])
        self.assertEqual(unfetched, ["down"])
        self.assertEqual(no_release, [])

    def test_error_record_matched_by_slug_not_just_exact_url(self):
        """_freshness_record_has_error() must also match via the raw record's own
        normalized slug, the same fallback build_manifest.py's compute_upstream() uses,
        not only an exact dict-key URL match."""
        raw_repositories = {
            "https://github.com/Example/Flaky.git": {
                "slug": "example/flaky", "partial_errors": {"releases": "503"},
            },
        }
        self.assertTrue(fp._freshness_record_has_error("https://github.com/example/flaky", raw_repositories))
        self.assertFalse(fp._freshness_record_has_error("https://github.com/example/other", raw_repositories))
        self.assertFalse(fp._freshness_record_has_error(None, raw_repositories))
        self.assertFalse(fp._freshness_record_has_error("https://github.com/example/flaky", None))


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
        # build_drift_report() requires github-freshness.json to exist and be
        # well-formed (N2b, fail closed); a clean, error-free default here keeps
        # every test below focused on its own scenario. Tests exercising N2b or
        # N2 override or remove this file explicitly.
        self._write_freshness_document({"errors": 0, "partial_errors": 0, "repositories": {}})

    def _write_freshness_document(self, document):
        (self.work_dir / "github-freshness.json").write_text(json.dumps(document), encoding="utf-8")

    def _write_manifest(self, path, rows):
        """`rows` is a list of (component_id, pin, latest, behind) or
        (component_id, pin, latest, behind, pushed_at) 5-tuples; pushed_at
        defaults to a fixed non-None date, i.e. "reliably fetched", unless a
        test explicitly passes None to represent no fetch evidence."""
        components = []
        for row in rows:
            component_id, pin, latest, behind, *rest = row
            pushed_at = rest[0] if rest else "2026-09-01"
            components.append({"id": component_id, "pin": pin,
                                "upstream": {"latest": latest, "pushed_at": pushed_at},
                                "pin_behind_upstream": behind})
        path.write_text(json.dumps({
            "foundation": [{"components": components}],
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
                              [("gitleaks", "8.30.0", None, False, None)])
        result = fp.build_drift_report(self.work_dir)
        self.assertEqual(result["drifted"], [])
        self.assertEqual(result["unfetched"], ["gitleaks"])
        self.assertEqual((self.work_dir / "drift-status.txt").read_text().strip(), "false")

    def test_n1_skills_ref_pin_change_survives_build_drift_report(self):
        """Exact N1 reproduction at the build_drift_report() level: a real
        catalogs/sota-convergence-shaped manifest pair for a no-release repository
        whose pin changed must show up in drift.md's table, not be silently
        absorbed into the "no reliable upstream data" section."""
        self._write_manifest(self.published_dir / "manifest-20260922.json",
                              [("skills-ref", "0.1.0", None, False, "2026-08-09")])
        self._write_manifest(self.work_dir / "manifest-20260923.json",
                              [("skills-ref", "0.1.1", None, False, "2026-08-09")])
        result = fp.build_drift_report(self.work_dir)
        self.assertEqual(result["drifted"], ["skills-ref"])
        self.assertEqual(result["unfetched"], [])
        drift_text = (self.work_dir / "drift.md").read_text()
        self.assertIn(fp.md_cell("skills-ref"), drift_text)
        self.assertIn(fp.md_cell("0.1.0"), drift_text)
        self.assertIn(fp.md_cell("0.1.1"), drift_text)

    def test_n2_partial_errors_surface_as_their_own_output_and_exclude_the_row(self):
        """Exact N2 reproduction at the build_drift_report() level: a 503 on the
        releases endpoint with a tag-endpoint fallback (partial_errors, not error)
        must both (a) exclude that component's row from drift, and (b) make
        upstream-partial-errors.txt nonzero so propose's job condition can refuse
        to run on this data."""
        self._write_freshness_document({
            "errors": 0, "partial_errors": 1,
            "repositories": {
                "https://github.com/example/flaky": {
                    "slug": "example/flaky", "latest_tag": "v1.2.0",
                    "partial_errors": {"releases": "503 Service Unavailable"},
                },
            },
        })
        self._write_manifest(self.published_dir / "manifest-20260922.json",
                              [("flaky", "1.1.0", "v1.1.0", False)])
        rebuilt_row = {"id": "flaky", "pin": "1.1.0", "repository": "https://github.com/example/flaky",
                       "upstream": {"latest": "v1.2.0", "pushed_at": "2026-09-20"}, "pin_behind_upstream": False}
        (self.work_dir / "manifest-20260923.json").write_text(
            json.dumps({"foundation": [{"components": [rebuilt_row]}], "trading": [], "counts": {}}),
            encoding="utf-8",
        )
        result = fp.build_drift_report(self.work_dir)
        self.assertEqual(result["drifted"], [])
        self.assertEqual(result["unfetched"], ["flaky"])
        self.assertEqual((self.work_dir / "upstream-partial-errors.txt").read_text().strip(), "1")

    def test_no_release_components_are_reported_but_not_counted_as_drift(self):
        self._write_manifest(self.published_dir / "manifest-20260922.json",
                              [("tavily-cli", "1.0.0", None, False)])
        self._write_manifest(self.work_dir / "manifest-20260923.json",
                              [("tavily-cli", "1.0.0", None, False)])
        result = fp.build_drift_report(self.work_dir)
        self.assertEqual(result["drifted"], [])
        self.assertEqual(result["unfetched"], [])
        self.assertEqual(result["no_release"], ["tavily-cli"])
        self.assertEqual((self.work_dir / "drift-status.txt").read_text().strip(), "false")
        self.assertIn(fp.md_cell("tavily-cli"), (self.work_dir / "drift.md").read_text())

    def test_upstream_error_count_reads_the_freshness_document(self):
        self._write_freshness_document({"errors": 3, "partial_errors": 0, "repositories": {}})
        self._write_manifest(self.published_dir / "manifest-20260922.json", [])
        self._write_manifest(self.work_dir / "manifest-20260923.json", [])
        fp.build_drift_report(self.work_dir)
        self.assertEqual((self.work_dir / "upstream-errors.txt").read_text().strip(), "3")

    def test_n4_drift_md_never_contains_the_absolute_work_dir_path(self):
        """N4: render_drift_markdown() must be given only rebuilt_path.name, never
        the full path -- work_dir here stands in for $RUNNER_TEMP/freshness, an
        absolute, host-specific path that must never land in committed evidence."""
        self._write_manifest(self.published_dir / "manifest-20260922.json",
                              [("gitleaks", "8.30.0", "v8.30.0", False)])
        self._write_manifest(self.work_dir / "manifest-20260923.json",
                              [("gitleaks", "8.30.1", "v8.30.1", False)])
        fp.build_drift_report(self.work_dir)
        drift_text = (self.work_dir / "drift.md").read_text()
        self.assertNotIn(str(self.work_dir), drift_text)
        self.assertIn("manifest-20260923.json", drift_text)

    def test_missing_freshness_document_raises_fail_closed(self):
        (self.work_dir / "github-freshness.json").unlink()
        self._write_manifest(self.published_dir / "manifest-20260922.json", [])
        self._write_manifest(self.work_dir / "manifest-20260923.json", [])
        with self.assertRaises(fp.FreshnessProposeError):
            fp.build_drift_report(self.work_dir)


class LoadFreshnessDocumentTests(unittest.TestCase):
    """N2b: a missing or broken github-freshness.json must fail closed (raise),
    never silently read as "zero errors"."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work_dir = Path(self.temporary.name)

    def test_raises_when_file_is_missing(self):
        with self.assertRaises(fp.FreshnessProposeError):
            fp._load_freshness_document(self.work_dir)

    def test_raises_on_malformed_json(self):
        (self.work_dir / "github-freshness.json").write_text("not json", encoding="utf-8")
        with self.assertRaises(fp.FreshnessProposeError):
            fp._load_freshness_document(self.work_dir)

    def test_raises_when_document_is_not_an_object(self):
        (self.work_dir / "github-freshness.json").write_text("[1, 2, 3]", encoding="utf-8")
        with self.assertRaises(fp.FreshnessProposeError):
            fp._load_freshness_document(self.work_dir)

    def test_loads_a_well_formed_document(self):
        (self.work_dir / "github-freshness.json").write_text(
            json.dumps({"errors": 0, "partial_errors": 0}), encoding="utf-8",
        )
        document = fp._load_freshness_document(self.work_dir)
        self.assertEqual(document, {"errors": 0, "partial_errors": 0})


class IntFieldTests(unittest.TestCase):
    def test_upstream_error_count_reads_a_valid_int(self):
        self.assertEqual(fp.upstream_error_count({"errors": 5}), 5)

    def test_upstream_error_count_raises_on_missing_field(self):
        with self.assertRaises(fp.FreshnessProposeError):
            fp.upstream_error_count({})

    def test_upstream_error_count_raises_on_non_int_field(self):
        with self.assertRaises(fp.FreshnessProposeError):
            fp.upstream_error_count({"errors": "3"})

    def test_upstream_error_count_raises_on_bool_field(self):
        # bool is a subclass of int in Python; must not silently pass as an int.
        with self.assertRaises(fp.FreshnessProposeError):
            fp.upstream_error_count({"errors": True})

    def test_upstream_partial_error_count_reads_a_valid_int(self):
        self.assertEqual(fp.upstream_partial_error_count({"partial_errors": 2}), 2)

    def test_upstream_partial_error_count_raises_on_missing_field(self):
        with self.assertRaises(fp.FreshnessProposeError):
            fp.upstream_partial_error_count({})


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
    # `add -A` skips files that match .gitignore, but the source checkout tracks some of
    # them on purpose (force-added evidence such as *.jsonl excerpts). Track those too so
    # the copy matches a clone: scripts/validate.py rejects a hash-listed file that is
    # ignored and untracked, because a commit would leave it out.
    tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, check=True).stdout
    present = [name for name in (os.fsdecode(item) for item in tracked.split(b"\0") if item)
               if (path / name).is_file() and not (path / name).is_symlink()]
    subprocess.run(["git", *git_env, "add", "--force", "--pathspec-from-file=-", "--pathspec-file-nul"],
                   cwd=path, check=True, input=b"\0".join(os.fsencode(name) for name in present))
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

    def test_freshness_job_exposes_drift_upstream_and_partial_errors_outputs(self):
        self.assertRegex(self.text, r"(?m)^\s+outputs:\s*\n\s+drift:\s*\$\{\{\s*steps\.diff\.outputs\.drift\s*\}\}")
        self.assertRegex(self.text, r"upstream_errors:\s*\$\{\{\s*steps\.diff\.outputs\.upstream_errors\s*\}\}")
        self.assertRegex(self.text, r"partial_errors:\s*\$\{\{\s*steps\.diff\.outputs\.partial_errors\s*\}\}")

    def test_diff_step_no_longer_hardcodes_a_dated_manifest_filename(self):
        self.assertNotIn("manifest-20260922.json", self.text)

    def test_diff_step_delegates_to_the_shared_module_instead_of_reimplementing_the_diff(self):
        body = self._job_body("freshness")
        self.assertIn("from scripts.freshness_propose import build_drift_report", body)
        # T3: the header text must not also be hand-duplicated in the YAML.
        self.assertNotIn("upstream latest (published)", body)

    def test_no_top_level_workflow_concurrency_group(self):
        # P2-3 (Codex): a workflow-level group with the default queue:single would let
        # a plain scheduled activation silently replace a pending manual open_pr:true
        # request. Concurrency now lives only on the `propose` job (see below), keyed
        # so that can never happen; `freshness` itself carries no concurrency
        # restriction at all (it only reads/reports, so parallel runs are harmless).
        top_level = self.text.split("\njobs:\n", 1)[0]
        self.assertNotRegex(top_level, r"(?m)^concurrency:")

    def test_propose_job_concurrency_is_job_scoped_and_keyed_on_opt_in(self):
        body = self._job_body("propose")
        match = re.search(r"(?m)^    concurrency:\n((?:      [^\n]*\n)+)", body)
        self.assertIsNotNone(match, "propose job needs its own concurrency block")
        block = match.group(1)
        self.assertIn(f"group: {EXPECTED_PROPOSE_CONCURRENCY_GROUP}", block)
        self.assertIn("cancel-in-progress: false", block)
        # queue: max is the documented fix for the same problem, but this
        # repository's pinned actionlint 1.7.12 rejects that key (checked
        # directly -- docs/decisions/2026-09-23-bot-pr-dispatch.md); it must not
        # be reintroduced as an actual concurrency key without re-verifying
        # actionlint support first (the surrounding prose may still *mention*
        # `queue:` to explain why it is not used).
        active_keys = [
            line.strip().split(":", 1)[0] for line in block.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        self.assertEqual(sorted(active_keys), sorted(["group", "cancel-in-progress"]))

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

    def test_pr_description_is_run_independent(self):
        """Codex verification of 52d136a: a branch-head check narrowed but could not
        close the overlap race (A checks, B pushes and edits, A edits). The body now
        embeds no run-specific report or receipt, so overlapping runs cannot leave it
        describing an older commit than the branch holds."""
        body = self._job_body("propose")
        pr_step = body[body.index("- name: Open or update the evidence PR"):body.index("- name: Note that this PR")]
        self.assertNotIn('cat "$RUNNER_TEMP/freshness/drift.md"', pr_step)
        self.assertNotIn("RECEIPT_PATH", pr_step)
        self.assertNotIn("current_sha", pr_step)
        self.assertIn("current head of", pr_step)
        body_block = pr_step[pr_step.index('body_file="$RUNNER_TEMP/freshness/pr-body.md"'):pr_step.index('} > "$body_file"')]
        for run_specific in ("GITHUB_RUN_ID", "github.run_id", "RUN_URL", "drift.md\"", "$(date"):
            self.assertNotIn(run_specific, body_block)

    def test_pr_create_race_falls_back_to_updating_the_existing_pr(self):
        """Codex verification of 250adae: two overlapping runs can both list no open PR;
        the second `gh pr create` then fails. It must fall back to updating the PR,
        and every update refreshes the dated title."""
        body = self._job_body("propose")
        self.assertIn('if [ -z "$existing" ] && ! gh pr create', body)
        self.assertIn('existing="$(find_open_pr)"', body)
        self.assertIn('gh pr edit "$existing" --title "$title" --body-file "$body_file"', body)

    def test_unfetched_wording_says_pin_changes_are_still_drift(self):
        report = fp.render_drift_markdown(
            "published.json", "rebuilt.json", {"counts": {}}, {"counts": {}},
            [("skills-ref", "0.1.0", "0.1.1", None, None, False, None)], ["skills-ref"], [])
        self.assertIn("a pin change on such a row is still", report)
        self.assertNotIn("are excluded from the drift count above", report)

    def test_propose_job_states_the_correct_approval_ui_path(self):
        # N3: approval happens on the PR itself -- the GITHUB_TOKEN page's banner in the
        # PR's merge box, selecting "Approve workflows to run" -- not via the Actions tab.
        body = self._job_body("propose")
        self.assertIn("approval banner", body)
        self.assertIn("Approve workflows to run", body)
        self.assertIn("merge box", body)
        self.assertNotIn("Approve and run workflow", body)
        self.assertIn("30 days", body)

    def test_propose_job_cites_the_current_github_token_exception_wording(self):
        # N3: the older paraphrase ("with the exception of workflow_dispatch and
        # repository_dispatch, will not create") must not reappear; the current
        # docs phrase it as "... will not create a new workflow run, with the
        # following exceptions: ...".
        body = self._job_body("propose")
        self.assertIn("with the following exceptions", body)
        outdated = [line for line in body.splitlines() if "with the exception of" in line]
        self.assertEqual(outdated, [])

    def test_force_create_branch_step_documents_that_it_discards_prior_commits(self):
        body = self._job_body("propose")
        branch_step_match = re.search(
            r"(?ms)^      - name: Observe the remote evidence branch.*?(?=^      - name:|\Z)", body,
        )
        self.assertIsNotNone(branch_step_match, "force-create-branch step not found")
        self.assertIn("discard", branch_step_match.group(0).lower())

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
