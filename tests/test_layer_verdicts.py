"""Synthetic-fixture tests for tools/sota-convergence/build_verdicts.py.

No network, no real catalogs -- a minimal fixture root is built per test.
Modules are loaded by file path (tools/sota-convergence is not a dotted-import
package name), matching the pattern already used by test_sota_convergence.py.
"""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL_DIR = ROOT / "tools" / "sota-convergence"


def load_module(name, filename):
    path = TOOL_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build_verdicts = load_module("build_verdicts", "build_verdicts.py")
# build_verdicts.py imports assert_no_leak/LeakDetected from build_manifest.py
# via its own sys.path-based "from build_manifest import ..." (see its
# module-level import comment); that registers a *separate* build_manifest
# module object in sys.modules than one this test might load independently
# by file path, so the LeakDetected class actually raised must come from the
# same module build_verdicts.py itself imported from.
LeakDetected = build_verdicts.assert_no_leak.__globals__["LeakDetected"]


def v2_row(**overrides):
    row = {
        "verdict_status": "pending_lanes",
        "winners": [], "alternatives": [],
        "overturn_protocol": {"fixture_paths": [], "metric": "", "arms": []},
        "lanes": {"claude": {"run_id": "", "sealed_sha256": ""},
                  "codex": {"run_id": "", "sealed_sha256": ""}, "agreement": "pending"},
        "open_gaps": [], "checked_at": "2026-09-22",
        "evidence_refs": ["receipt.json"], "limitations": ["One input"],
        "overturn_when": "A matched task improves quality",
        "candidates": [{"name": "Selected", "repository": "https://github.com/example/selected",
                        "disposition": "selected", "rationale": "Fits",
                        "evidence_kind": "native_execution", "evidence_refs": []}],
    }
    row.update(overrides)
    return row


class LayerVerdictFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.foundation_row = v2_row(catalog="foundation", layer_id="native-clients", title="Native clients",
                                     requirement="Run tasks", current_choice="Codex", decision="retain",
                                     rationale="Native task evidence")
        self.trading_row = v2_row(catalog="us-equities", layer_id="market-data-reference",
                                  title="Market data", group="data-research", requirement="Freeze the universe",
                                  current_choice="alpaca-py", decision="retain", rationale="Official SDK")
        self.write("catalogs/landscape/foundation.json", {
            "schema_version": 2, "checked_at": "2026-09-22", "scope": "Fixture",
            "layers": [self.foundation_row],
        })
        self.write("catalogs/landscape/us-equities.json", {
            "schema_version": 2, "checked_at": "2026-09-22", "scope": "Fixture",
            "layers": [self.trading_row], "domain_rows": [],
        })
        self.write("catalogs/sota-convergence/manifest-20260922.json", {
            "foundation": [{"layer": "native-clients", "title": "Native clients", "components": [
                {"id": "codex-native-sdk", "pin": "1.0", "upstream": {"latest": "1.0"},
                 "review_status": "confirmed_default", "pin_behind_upstream": False}]}],
            "trading": [{"layer": "market-data-reference", "entries": [
                {"id": "alpaca-py", "pin": "3.0", "upstream": {"latest": "3.0"},
                 "review_status": "confirmed_default", "pin_behind_upstream": False}]}],
        })
        self.write("adoption/manifest.json", {"recipe_map": {"alpaca-py": "recipes/README.md"}})
        handbook = self.root / "docs" / "grand-catalog-handbook.md"
        handbook.parent.mkdir(parents=True, exist_ok=True)
        handbook.write_text("# Grand catalog handbook\n\nExisting content.\n", encoding="utf-8")

    def write(self, path, value):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value), encoding="utf-8")

    def handbook_text(self):
        return (self.root / "docs" / "grand-catalog-handbook.md").read_text(encoding="utf-8")

    def out_path(self):
        return self.root / "catalogs/sota-convergence/layer-verdicts-20260922.json"


class BuildVerdictsTests(LayerVerdictFixture):
    def test_check_fails_before_the_output_exists(self):
        exit_code = build_verdicts.main(["--check", "--root", str(self.root)])
        self.assertEqual(exit_code, 1)
        self.assertFalse(self.out_path().exists())

    def test_write_then_check_round_trips_on_a_fixture_root(self):
        self.assertEqual(build_verdicts.main(["--write", "--root", str(self.root)]), 0)
        self.assertTrue(self.out_path().exists())
        document = json.loads(self.out_path().read_text(encoding="utf-8"))
        self.assertEqual(document["counts"]["foundation"]["layers"], 1)
        self.assertEqual(document["counts"]["us-equities"]["layers"], 1)
        self.assertEqual(build_verdicts.main(["--check", "--root", str(self.root)]), 0)

    def test_check_is_deterministic_and_idempotent_across_repeated_runs(self):
        self.assertEqual(build_verdicts.main(["--write", "--root", str(self.root)]), 0)
        first_json = self.out_path().read_text(encoding="utf-8")
        first_handbook = self.handbook_text()
        for _ in range(3):
            self.assertEqual(build_verdicts.main(["--check", "--root", str(self.root)]), 0)
        self.assertEqual(self.out_path().read_text(encoding="utf-8"), first_json)
        self.assertEqual(self.handbook_text(), first_handbook)
        # Re-running --write on an already-current fixture root must not grow
        # the handbook file (the marker-replacement bug this guards against
        # appended a fresh trailing newline on every run).
        self.assertEqual(build_verdicts.main(["--write", "--root", str(self.root)]), 0)
        self.assertEqual(self.handbook_text(), first_handbook)

    def test_marker_insertion_when_absent_then_reused_on_rerun(self):
        self.assertNotIn(build_verdicts.MARKER_BEGIN, self.handbook_text())
        self.assertEqual(build_verdicts.main(["--write", "--root", str(self.root)]), 0)
        text = self.handbook_text()
        self.assertIn(build_verdicts.MARKER_BEGIN, text)
        self.assertIn(build_verdicts.MARKER_END, text)
        self.assertIn("## Per-layer verdicts (generated)", text)
        self.assertIn("Existing content.", text)  # original content preserved
        self.assertEqual(text.count(build_verdicts.MARKER_BEGIN), 1)
        # A second write must replace the same block, not append another one.
        self.assertEqual(build_verdicts.main(["--write", "--root", str(self.root)]), 0)
        self.assertEqual(self.handbook_text().count(build_verdicts.MARKER_BEGIN), 1)

    def test_pending_rows_render_as_pending_in_the_handbook_table(self):
        self.assertEqual(build_verdicts.main(["--write", "--root", str(self.root)]), 0)
        text = self.handbook_text()
        self.assertIn("| native-clients | - | pending |", text)
        self.assertIn("| market-data-reference | data-research | pending |", text)
        # The status *cell* renders "pending", never the internal
        # "pending_lanes" string (which may still appear in prose, e.g. this
        # generator's own scope sentence).
        for line in text.splitlines():
            if line.startswith("| native-clients") or line.startswith("| market-data-reference"):
                self.assertNotIn("pending_lanes", line)

    def test_leak_refusal_stops_the_write(self):
        # "rationale" is a v1 field the generator does not republish; the leak
        # must be injected into a field build_verdict_row() actually carries
        # into the generated document ("overturn_when") for this to exercise
        # the writer's own leak check rather than merely proving the field is
        # dropped.
        leaking = json.loads((self.root / "catalogs/landscape/foundation.json").read_text())
        leaking["layers"][0]["overturn_when"] = "Selected using key APCA1234567890ABCDEF"
        self.write("catalogs/landscape/foundation.json", leaking)
        with self.assertRaises(LeakDetected):
            build_verdicts.main(["--write", "--root", str(self.root)])
        self.assertFalse(self.out_path().exists())

    def test_host_path_is_sanitized_rather_than_leaking(self):
        with_path = json.loads((self.root / "catalogs/landscape/foundation.json").read_text())
        with_path["layers"][0]["overturn_when"] = 'Reviewed at "/home/example/code/native-agent-stack/x.json"'
        self.write("catalogs/landscape/foundation.json", with_path)
        self.assertEqual(build_verdicts.main(["--write", "--root", str(self.root)]), 0)
        self.assertNotIn("/home/", self.out_path().read_text(encoding="utf-8"))
        self.assertNotIn("/home/", self.handbook_text())

    def test_sota_components_and_recipe_refs_are_joined_from_the_manifest(self):
        row = json.loads((self.root / "catalogs/landscape/us-equities.json").read_text())
        row["layers"][0]["winners"] = [{
            "component_id": "alpaca-py", "repository": "https://github.com/alpacahq/alpaca-py",
            "pin": "3.0", "evidence_class": "native_proven", "why_selected": "Official SDK",
            "evidence_refs": [], "recipe_ref": "alpaca-py",
            "platform_status": {"linux-wsl2-x86_64": "accepted", "macos-arm64": "untested"},
        }]
        self.write("catalogs/landscape/us-equities.json", row)
        self.assertEqual(build_verdicts.main(["--write", "--root", str(self.root)]), 0)
        document = json.loads(self.out_path().read_text(encoding="utf-8"))
        trading_row = document["catalogs"]["us-equities"][0]
        self.assertEqual(trading_row["sota_components"][0]["id"], "alpaca-py")
        self.assertEqual(trading_row["sota_components"][0]["pin"], "3.0")
        self.assertEqual(trading_row["recipe_refs"], ["alpaca-py"])

    def test_narrative_renders_recorded_and_pending_rows(self):
        foundation = json.loads((self.root / "catalogs/landscape/foundation.json").read_text())
        row = foundation["layers"][0]
        row["verdict_status"] = "recorded"
        row["winners"] = [{
            "component_id": "codex-native-sdk", "repository": "https://github.com/openai/codex",
            "pin": "1.0", "evidence_class": "native_proven", "why_selected": "Native execution evidence",
            "evidence_refs": [], "recipe_ref": "recipes/README.md",
            "platform_status": {"linux-wsl2-x86_64": "accepted", "macos-arm64": "untested"},
        }]
        row["alternatives"] = [{
            "name": "Other tool", "repository": "https://github.com/example/other",
            "disposition": "conditional", "why_not_default": "Not selected on the retained evidence",
            "evidence_class": "source_review", "source": "lane:codex",
        }]
        row["verdict_overturn_when"] = "See tests/test_layer_verdicts.py for the fixture that would overturn this."
        row["open_gaps"] = ["codex lane absent for this layer"]
        row["lanes"] = {"claude": {"run_id": "foundation-native-clients-20260922", "sealed_sha256": "a" * 64},
                        "codex": {"run_id": "", "sealed_sha256": ""}, "agreement": "codex_absent"}
        self.write("catalogs/landscape/foundation.json", foundation)

        self.assertEqual(build_verdicts.main(["--write", "--root", str(self.root)]), 0)
        text = self.handbook_text()
        self.assertIn("#### Native clients (native-clients)", text)
        self.assertIn("- codex-native-sdk @ 1.0 — Native execution evidence", text)
        self.assertIn("- Other tool (conditional) — Not selected on the retained evidence", text)
        self.assertIn("Overturn when: See tests/test_layer_verdicts.py for the fixture that would overturn this.",
                      text)
        self.assertIn("- codex lane absent for this layer", text)
        self.assertIn("Lanes: codex_absent (claude: foundation-native-clients-20260922; codex: -)", text)
        # The still-pending trading row renders as a single "pending -- ..." line.
        self.assertIn("- **Market data** (market-data-reference): pending — no lane has run", text)
        # --check recomputes and covers the narrative, not just the table.
        self.assertEqual(build_verdicts.main(["--check", "--root", str(self.root)]), 0)
        foundation["layers"][0]["verdict_overturn_when"] = "A different, untracked overturn text"
        self.write("catalogs/landscape/foundation.json", foundation)
        self.assertEqual(build_verdicts.main(["--check", "--root", str(self.root)]), 1)

    def test_narrative_catalog_heading_nests_above_its_row_blocks(self):
        # render_narrative's own "<catalog> (per-layer narrative)" heading
        # must sit at a shallower Markdown level ("###") than every row's
        # "#### <title> (<layer_id>)" block, and distinct from render_table's
        # own "### {catalog}" table heading text, so the outline actually
        # nests instead of placing the section heading beside its rows.
        foundation = json.loads((self.root / "catalogs/landscape/foundation.json").read_text())
        row = foundation["layers"][0]
        row["verdict_status"] = "recorded"
        row["winners"] = [{
            "component_id": "codex-native-sdk", "repository": "https://github.com/openai/codex",
            "pin": "1.0", "evidence_class": "native_proven", "why_selected": "Native execution evidence",
            "evidence_refs": [], "recipe_ref": "recipes/README.md",
            "platform_status": {"linux-wsl2-x86_64": "accepted", "macos-arm64": "untested"},
        }]
        row["alternatives"] = []
        self.write("catalogs/landscape/foundation.json", foundation)

        self.assertEqual(build_verdicts.main(["--write", "--root", str(self.root)]), 0)
        text = self.handbook_text()
        self.assertIn("### foundation (per-layer narrative)", text)
        self.assertNotIn("#### foundation (per-layer narrative)", text)
        narrative_heading = text.index("### foundation (per-layer narrative)")
        row_heading = text.index("#### Native clients (native-clients)")
        self.assertLess(narrative_heading, row_heading)


if __name__ == "__main__":
    unittest.main()
