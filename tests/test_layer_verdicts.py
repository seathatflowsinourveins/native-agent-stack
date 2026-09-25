"""Synthetic-fixture tests for tools/sota-convergence/build_verdicts.py.

No network, no real catalogs -- a minimal fixture root is built per test.
Modules are loaded by file path (tools/sota-convergence is not a dotted-import
package name), matching the pattern already used by test_sota_convergence.py.
"""
import contextlib
import hashlib
import importlib.util
import io
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

    def later_wave(self):
        """A non-grandfathered wave (20260923) with the same manifest: the current wave can be
        rewritten, while a registered grandfathered one (20260922, which the fixture's pending
        rows name) never is."""
        if not self.out_path().exists():
            self.assertEqual(build_verdicts.main(["--write", "--root", str(self.root)]), 0)
        manifest = (self.root / "catalogs/sota-convergence/manifest-20260922.json").read_text(encoding="utf-8")
        (self.root / "catalogs/sota-convergence/manifest-20260923.json").write_text(manifest, encoding="utf-8")
        return ["--root", str(self.root), "--run-id", "20260923"]

    def test_check_is_deterministic_and_idempotent_across_repeated_runs(self):
        wave = self.later_wave()
        out_path = self.root / "catalogs/sota-convergence/layer-verdicts-20260923.json"
        self.assertEqual(build_verdicts.main(["--write", *wave]), 0)
        first_json = out_path.read_text(encoding="utf-8")
        first_handbook = self.handbook_text()
        for _ in range(3):
            self.assertEqual(build_verdicts.main(["--check", "--root", str(self.root)]), 0)
        self.assertEqual(out_path.read_text(encoding="utf-8"), first_json)
        self.assertEqual(self.handbook_text(), first_handbook)
        # Re-running --write on an already-current fixture root must not grow
        # the handbook file (the marker-replacement bug this guards against
        # appended a fresh trailing newline on every run).
        self.assertEqual(build_verdicts.main(["--write", *wave]), 0)
        self.assertEqual(self.handbook_text(), first_handbook)
        self.assertEqual(out_path.read_text(encoding="utf-8"), first_json)

    def test_a_registered_grandfathered_wave_is_never_rewritten_even_as_the_newest(self):
        # Review finding: with 20260922 the only (so current) wave, --write rewrote its document
        # and replaced its registered sha256; a grandfathered wave is frozen once registered.
        self.assertEqual(build_verdicts.main(["--write", "--root", str(self.root)]), 0)
        registry_before = (self.root / build_verdicts.WAVE_REGISTRY).read_bytes()
        document_before = self.out_path().read_bytes()
        for argv in (["--write", "--root", str(self.root)],
                     ["--write", "--root", str(self.root), "--run-id", "20260922"]):
            with self.assertRaisesRegex(SystemExit, "grandfathered"):
                build_verdicts.main(argv)
        self.assertEqual((self.root / build_verdicts.WAVE_REGISTRY).read_bytes(), registry_before)
        self.assertEqual(self.out_path().read_bytes(), document_before)

    def test_run_id_option_derives_a_dated_manifest_and_out_path_and_id_field(self):
        self.write("catalogs/sota-convergence/manifest-20260923.json", {
            "foundation": [{"layer": "native-clients", "title": "Native clients", "components": [
                {"id": "codex-native-sdk", "pin": "2.0", "upstream": {"latest": "2.0"},
                 "review_status": "confirmed_default", "pin_behind_upstream": False}]}],
            "trading": [{"layer": "market-data-reference", "entries": [
                {"id": "alpaca-py", "pin": "3.0", "upstream": {"latest": "3.0"},
                 "review_status": "confirmed_default", "pin_behind_upstream": False}]}],
        })
        self.assertEqual(build_verdicts.main(
            ["--write", "--root", str(self.root), "--run-id", "20260923"]), 0)
        out_path = self.root / "catalogs/sota-convergence/layer-verdicts-20260923.json"
        self.assertTrue(out_path.is_file())
        document = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(document["id"], "layer-verdicts-20260923")
        # A later run's --manifest join is used (2.0 pin), not the default 2026-09-22 one (1.0).
        foundation_row = next(row for row in document["catalogs"]["foundation"]
                              if row["layer_id"] == "native-clients")
        self.assertEqual(foundation_row["sota_components"][0]["pin"], "2.0")
        # The default 2026-09-22 output is untouched by a --run-id 20260923 write.
        self.assertFalse(self.out_path().exists())
        self.assertEqual(build_verdicts.main(
            ["--check", "--root", str(self.root), "--run-id", "20260923"]), 0)

    def test_explicit_manifest_and_out_override_the_run_id_derived_defaults(self):
        self.write("catalogs/sota-convergence/manifest-custom.json", {
            "foundation": [{"layer": "native-clients", "title": "Native clients", "components": [
                {"id": "codex-native-sdk", "pin": "9.0", "upstream": {"latest": "9.0"},
                 "review_status": "confirmed_default", "pin_behind_upstream": False}]}],
            "trading": [{"layer": "market-data-reference", "entries": [
                {"id": "alpaca-py", "pin": "3.0", "upstream": {"latest": "3.0"},
                 "review_status": "confirmed_default", "pin_behind_upstream": False}]}],
        })
        custom_out = self.root / "catalogs/sota-convergence/layer-verdicts-custom-out.json"
        self.assertEqual(build_verdicts.main([
            "--write", "--root", str(self.root),
            "--manifest", str(self.root / "catalogs/sota-convergence/manifest-custom.json"),
            "--out", str(custom_out),
        ]), 0)
        self.assertTrue(custom_out.is_file())
        document = json.loads(custom_out.read_text(encoding="utf-8"))
        # --id still uses the default run-id (20260922) since --run-id was not given.
        self.assertEqual(document["id"], "layer-verdicts-20260922")
        foundation_row = next(row for row in document["catalogs"]["foundation"]
                              if row["layer_id"] == "native-clients")
        self.assertEqual(foundation_row["sota_components"][0]["pin"], "9.0")
        self.assertFalse(self.out_path().exists())

    def test_malformed_run_id_is_rejected_before_any_write(self):
        for bad in ("2026-09-23", "../escape", "20260923/x"):
            with self.assertRaises(SystemExit):
                build_verdicts.main(["--write", "--root", str(self.root), "--run-id", bad])
            self.assertFalse((self.root / f"catalogs/sota-convergence/layer-verdicts-{bad}.json").exists())

    def test_marker_insertion_when_absent_then_reused_on_rerun(self):
        self.assertNotIn(build_verdicts.MARKER_BEGIN, self.handbook_text())
        self.assertEqual(build_verdicts.main(["--write", "--root", str(self.root)]), 0)
        text = self.handbook_text()
        self.assertIn(build_verdicts.MARKER_BEGIN, text)
        self.assertIn(build_verdicts.MARKER_END, text)
        self.assertIn("## Per-layer verdicts (generated)", text)
        self.assertIn("Existing content.", text)  # original content preserved
        self.assertEqual(text.count(build_verdicts.MARKER_BEGIN), 1)
        # A second write (of the current, non-grandfathered wave) must replace the same block,
        # not append another one.
        self.assertEqual(build_verdicts.main(["--write", *self.later_wave()]), 0)
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

    def test_no_selection_row_renders_as_no_selection_in_the_narrative(self):
        foundation = json.loads((self.root / "catalogs/landscape/foundation.json").read_text())
        row = foundation["layers"][0]
        row["verdict_status"] = "no_selection"
        row["open_gaps"] = ["no qualified candidate on the retained evidence"]
        self.write("catalogs/landscape/foundation.json", foundation)
        self.assertEqual(build_verdicts.main(["--write", "--root", str(self.root)]), 0)
        text = self.handbook_text()
        self.assertIn("(native-clients): no selection — no qualified candidate on the retained evidence", text)

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


class WaveFreezeTests(LayerVerdictFixture):
    """Per-wave CI (2026-09-23 peer audit): a later wave must not break the default
    ``--check``. Each wave document is frozen and hash-registered; only the newest wave and
    the handbook block are regenerated from the current rows."""

    LATER = "20260923"

    def later_manifest(self):
        self.write(f"catalogs/sota-convergence/manifest-{self.LATER}.json", {
            "foundation": [{"layer": "native-clients", "title": "Native clients", "components": [
                {"id": "codex-native-sdk", "pin": "2.0", "upstream": {"latest": "2.0"},
                 "review_status": "confirmed_default", "pin_behind_upstream": False}]}],
            "trading": [{"layer": "market-data-reference", "entries": [
                {"id": "alpaca-py", "pin": "3.0", "upstream": {"latest": "3.0"},
                 "review_status": "confirmed_default", "pin_behind_upstream": False}]}],
        })

    def record_later_wave_on_the_foundation_row(self, gap="re-recorded in the later wave"):
        """What record_verdicts.py --run-id 20260923 --write does to a row: new lanes pointing
        at the later sealed base and changed verdict fields; the trading row stays on 20260922."""
        foundation = json.loads((self.root / "catalogs/landscape/foundation.json").read_text())
        row = foundation["layers"][0]
        row["open_gaps"] = [gap]
        row["checked_at"] = "2026-09-23"
        row["lanes"] = {"claude": {"run_id": f"foundation-native-clients-{self.LATER}", "sealed_sha256": ""},
                        "codex": {"run_id": "", "sealed_sha256": ""}, "agreement": "pending",
                        "sealed_base": f"evidence/artifacts/layer-verdicts-{self.LATER}"}
        self.write("catalogs/landscape/foundation.json", foundation)

    def two_waves(self):
        self.assertEqual(build_verdicts.main(["--write", "--root", str(self.root)]), 0)
        self.first_wave_bytes = self.out_path().read_bytes()
        self.later_manifest()
        self.record_later_wave_on_the_foundation_row()
        self.assertEqual(build_verdicts.main(
            ["--write", "--root", str(self.root), "--run-id", self.LATER, "--checked-at", "2026-09-23"]), 0)

    def later_out(self):
        return self.root / f"catalogs/sota-convergence/layer-verdicts-{self.LATER}.json"

    def check(self, *extra):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = build_verdicts.main(["--check", "--root", str(self.root), *extra])
        return code, output.getvalue()

    def test_a_later_wave_leaves_the_default_check_passing(self):
        self.two_waves()
        code, output = self.check()
        self.assertEqual(code, 0, output)
        # The frozen first wave was not regenerated from the changed rows.
        self.assertEqual(self.out_path().read_bytes(), self.first_wave_bytes)
        later = json.loads(self.later_out().read_text(encoding="utf-8"))
        self.assertEqual(later["id"], f"layer-verdicts-{self.LATER}")
        self.assertIn("re-recorded in the later wave", self.handbook_text())

    def test_each_wave_is_registered_by_hash(self):
        self.two_waves()
        registry = json.loads((self.root / build_verdicts.WAVE_REGISTRY).read_text(encoding="utf-8"))
        by_run = {wave["run_id"]: wave for wave in registry["waves"]}
        self.assertEqual(set(by_run), {"20260922", self.LATER})
        self.assertEqual(by_run["20260922"]["sha256"], hashlib.sha256(self.first_wave_bytes).hexdigest())
        self.assertEqual(by_run[self.LATER]["sha256"], hashlib.sha256(self.later_out().read_bytes()).hexdigest())

    def test_a_hand_edited_frozen_wave_fails_its_registered_hash(self):
        self.two_waves()
        self.out_path().write_bytes(self.first_wave_bytes.replace(b'"schema_version": 1', b'"schema_version":  1'))
        code, output = self.check()
        self.assertEqual(code, 1)
        self.assertIn("registered sha256", output)

    def test_a_row_still_naming_the_frozen_wave_cannot_change(self):
        self.two_waves()
        trading = json.loads((self.root / "catalogs/landscape/us-equities.json").read_text())
        trading["layers"][0]["open_gaps"] = ["edited after the wave was frozen"]
        self.write("catalogs/landscape/us-equities.json", trading)
        code, output = self.check()
        self.assertEqual(code, 1)
        self.assertIn("us-equities/market-data-reference", output)
        self.assertIn("20260922", output)

    def test_frozen_row_comparison_is_type_strict(self):
        # A type-only rewrite (1 -> 1.0 or True) must not compare equal to the frozen entry.
        same_json = build_verdicts.__dict__["same_json"]
        self.assertTrue(same_json({"a": 1, "b": [True]}, {"b": [True], "a": 1}))
        for rewritten in ({"a": 1.0, "b": [True]}, {"a": True, "b": [True]}, {"a": 1, "b": [1]}):
            self.assertFalse(same_json({"a": 1, "b": [True]}, rewritten))

    def test_the_newest_wave_is_regenerated_from_the_current_rows(self):
        self.two_waves()
        self.record_later_wave_on_the_foundation_row(gap="a second correction in the same wave")
        self.assertEqual(self.check()[0], 1)
        # --write without --run-id rewrites the current (newest) wave only.
        self.assertEqual(build_verdicts.main(["--write", "--root", str(self.root)]), 0)
        self.assertEqual(self.check()[0], 0)
        self.assertEqual(self.out_path().read_bytes(), self.first_wave_bytes)
        self.assertIn("a second correction in the same wave", self.later_out().read_text(encoding="utf-8"))

    def test_an_older_wave_cannot_be_rewritten(self):
        self.two_waves()
        with self.assertRaises(SystemExit):
            build_verdicts.main(["--write", "--root", str(self.root), "--run-id", "20260922"])
        self.assertEqual(self.out_path().read_bytes(), self.first_wave_bytes)

    def test_rows_of_an_unregistered_wave_fail_the_check(self):
        self.assertEqual(build_verdicts.main(["--write", "--root", str(self.root)]), 0)
        self.later_manifest()
        self.record_later_wave_on_the_foundation_row()
        code, output = self.check()
        self.assertEqual(code, 1)
        self.assertIn(self.LATER, output)


# The committed grandfathered wave (catalog main 38847e5), pinned so that no tool run or hand edit
# can change it without failing CI's python3 -m unittest, independent of whether a later wave exists.
GRANDFATHERED_DOCUMENT = "catalogs/sota-convergence/layer-verdicts-20260922.json"
GRANDFATHERED_DOCUMENT_SHA256 = "2fef6da7468a8e97a319fdc6f75f73374cd34b412bf93de90fd0c2a7504159de"
GRANDFATHERED_SEALED_BASE = "evidence/artifacts/layer-verdicts-20260922"
GRANDFATHERED_SEALED_FILE_COUNT = 122
# sha256 of the "<sha256>  <path relative to the sealed base>\n" listing of every file there, sorted.
GRANDFATHERED_SEALED_LISTING_SHA256 = "d1ba4bc301d3fc73fbb89d368f4301867e074649816fe4a5ab029be1f9840b3f"


class GrandfatheredWavePinTests(unittest.TestCase):
    """Review finding: the 2026-09-22 wave was frozen only once a later wave existed, so a
    --run-id-less record_verdicts --write plus build_verdicts --write could rewrite it and its
    registered hash while --check and landscape.py (grandfathered) still passed."""

    def test_the_grandfathered_rule_covers_only_the_20260922_wave(self):
        from scripts.landscape import GRANDFATHERED_RUN_IDS
        self.assertEqual(GRANDFATHERED_RUN_IDS, frozenset({"20260922"}))

    def test_the_committed_wave_document_and_its_registration_are_unchanged(self):
        self.assertEqual(hashlib.sha256((ROOT / GRANDFATHERED_DOCUMENT).read_bytes()).hexdigest(),
                         GRANDFATHERED_DOCUMENT_SHA256)
        registry = json.loads((ROOT / build_verdicts.WAVE_REGISTRY).read_text(encoding="utf-8"))
        wave = next(item for item in registry["waves"] if item["run_id"] == "20260922")
        self.assertEqual((wave["path"], wave["sha256"]), (GRANDFATHERED_DOCUMENT, GRANDFATHERED_DOCUMENT_SHA256))

    def test_the_committed_sealed_directory_is_unchanged_and_has_no_run_manifest(self):
        base = ROOT / GRANDFATHERED_SEALED_BASE
        files = sorted(path for path in base.rglob("*") if path.is_file())
        listing = "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(base).as_posix()}\n"
                          for path in files)
        self.assertFalse((base / "run-manifest.json").exists(), "no run manifest is fabricated for 20260922")
        self.assertEqual(len(files), GRANDFATHERED_SEALED_FILE_COUNT)
        self.assertEqual(hashlib.sha256(listing.encode("utf-8")).hexdigest(), GRANDFATHERED_SEALED_LISTING_SHA256)

    def test_the_tools_refuse_to_rewrite_the_committed_wave(self):
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(SystemExit, "grandfathered"):
            build_verdicts.main(["--write", "--root", str(ROOT), "--run-id", "20260922"])
        record_verdicts = load_module("record_verdicts_pin", "record_verdicts.py")
        with tempfile.TemporaryDirectory() as work_dir, self.assertRaisesRegex(SystemExit, "grandfathered"):
            record_verdicts.main(["--root", str(ROOT), "--work-dir", work_dir, "--run-id", "20260922", "--write"])
        self.test_the_committed_wave_document_and_its_registration_are_unchanged()
        self.test_the_committed_sealed_directory_is_unchanged_and_has_no_run_manifest()


if __name__ == "__main__":
    unittest.main()
