"""Tests for scripts/new_host_grand_list.py: the join covers every matrix
winner, the per-platform bootstrap-pin flags follow the pin files, projected
tier strings reduce to their result, and the checked-in outputs are fresh."""

from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

from scripts import new_host_grand_list as g

ROOT = Path(__file__).resolve().parents[1]

REPO_ROOT = Path(__file__).resolve().parents[1]


class TierValueTests(unittest.TestCase):
    def test_arrow_result(self):
        self.assertEqual(g.tier_value("vram_gb=24 >= 20 -> large-32b-q4"), "large-32b-q4")

    def test_equals_result(self):
        self.assertEqual(g.tier_value("min(16, 32 - 2) = 16"), "16")

    def test_passthrough(self):
        self.assertEqual(g.tier_value(12), 12)
        self.assertIsNone(g.tier_value(None))


class RepoKeyTests(unittest.TestCase):
    def test_release_and_tree_urls_share_a_key(self):
        self.assertEqual(g.repo_key("https://github.com/tobi/qmd/releases/tag/v2.8.3"), "tobi/qmd")
        self.assertEqual(g.repo_key("https://github.com/openai/codex-plugin-cc/tree/v1.0.6"), "openai/codex-plugin-cc")
        self.assertEqual(g.repo_key("https://github.com/Owner/Repo.git"), "owner/repo")

    def test_only_the_github_host_counts(self):
        self.assertIsNone(g.github_repo("https://evil.example/github.com/owner/repo"))
        self.assertIsNone(g.github_repo("https://github.com.evil.example/owner/repo"))
        self.assertEqual(g.github_repo("https://github.com/cli/cli/releases/download/v2.101.0/gh.tar.gz"), "cli/cli")


class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = g.build()
        cls.matrix = json.loads((REPO_ROOT / "catalogs/landscape/component-evidence-matrix.json").read_text(encoding="utf-8"))

    def test_every_matrix_winner_appears_once(self):
        expected = sorted((r["layer_id"], w["component_id"]) for r in self.matrix["rows"] for w in r["winners"])
        got = sorted((l["layer_id"], w["component_id"]) for l in self.data["layers"] for w in l["winners"])
        self.assertEqual(got, expected)

    def test_e2e_state_copied_from_matrix(self):
        states = {(r["layer_id"], w["component_id"], p): (w.get("platforms") or {}).get(p, {}).get("e2e_state")
                  for r in self.matrix["rows"] for w in r["winners"] for p in g.PLATFORMS}
        for layer in self.data["layers"]:
            for w in layer["winners"]:
                for p in g.PLATFORMS:
                    self.assertEqual(w["platforms"][p]["e2e_state"], states[(layer["layer_id"], w["component_id"], p)])

    def _winner(self, component_id):
        return next(w for l in self.data["layers"] for w in l["winners"] if w["component_id"] == component_id)

    def test_pinned_by_id_alias_or_repository(self):
        # gh and uv are pinned under other ids; the join must still find them.
        for cid in ("candidate:cli-cli", "candidate:astral-sh-uv", "ai-memory", "codex"):
            self.assertTrue(self._winner(cid)["platforms"]["linux-wsl2-x86_64"]["bootstrap_pinned"], cid)
        self.assertTrue(self._winner("foundation-ai-memory")["platforms"]["linux-wsl2-x86_64"]["bootstrap_pinned"])

    def test_trading_ids_map_to_install_profiles(self):
        self.assertIn("trading-nautilus", self._winner("nautilustrader")["install_profiles"])
        self.assertIn("foundation-cpu", self._winner("foundation-ai-memory")["install_profiles"])

    def test_manifest_join_reports_behind_pins(self):
        w = self._winner("ai-memory")
        self.assertTrue(w["manifest_joined"])
        self.assertIsNotNone(w["upstream_latest"])

    def test_summary_counts(self):
        s = self.data["summary"]
        self.assertEqual(s["winners"], sum(len(l["winners"]) for l in self.data["layers"]))
        self.assertEqual(s["layers"]["foundation"] + s["layers"]["us-equities"], len(self.data["layers"]))

    def test_rendered_markdown_has_every_layer(self):
        md = g.render_md(self.data)
        for layer in self.data["layers"]:
            self.assertIn(layer["title"].replace("|", "\\|"), md)


class FreshnessTests(unittest.TestCase):
    def test_checked_in_outputs_are_fresh(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            code = g.main(["--check"])
        self.assertEqual(code, 0, err.getvalue())


class BuildHostsTests(unittest.TestCase):
    """A native_proven hosts[] entry whose .json evidence file is missing must fail loudly
    (exit 1 via SystemExit), not silently give null tiers; every host's own `measured` block
    must carry through unchanged."""

    def test_missing_native_proven_json_evidence_raises(self):
        hw = {"hosts": [{
            "id": "widget-20260101", "label": "widget", "evidence_class": "native_proven",
            "evidence": "evidence/artifacts/hw-profiles/does-not-exist-xyz/profile.json",
        }]}
        with self.assertRaises(SystemExit) as ctx:
            g.build_hosts(hw)
        self.assertIn("does not exist", str(ctx.exception))

    def test_native_proven_prose_evidence_does_not_require_a_file(self):
        # Mirrors the shipped github-macos-15-arm64-runner entry: native_proven with a prose
        # citation (not a .json report path) is not held to the file-exists check.
        hw = {"hosts": [{
            "id": "github-macos-15-arm64-runner", "label": "runner", "evidence_class": "native_proven",
            "evidence": "GitHub Actions run 1 (some workflow): a citation, not a file path.",
        }]}
        hosts = g.build_hosts(hw)
        self.assertIsNone(hosts[0]["measured_tiers"])

    def test_measured_block_is_carried_through_including_nested_mlx_smoke(self):
        hw = {"hosts": [{
            "id": "github-macos-15-arm64-runner", "label": "runner", "evidence_class": "native_proven",
            "evidence": "a citation, not a file", "measured": {
                "cpu_brand": "Apple M1 (Virtual)", "cores": 3, "unified_memory_gb": 7.0,
                "mlx_smoke": {"model": "mlx-community/Qwen2.5-0.5B-Instruct-4bit",
                             "revision": "a5339a4131f135d0fdc6a5c8b5bbed2753bbe0f3",
                             "tokens_per_second": 146.57, "generation_tokens": 32},
            },
        }]}
        hosts = g.build_hosts(hw)
        self.assertEqual(hosts[0]["measured"]["cores"], 3)
        self.assertEqual(hosts[0]["measured"]["mlx_smoke"]["tokens_per_second"], 146.57)

    def test_labelled_projection_host_has_no_measured_block(self):
        hw = {"hosts": [{"id": "wsl-projected", "label": "x", "evidence_class": "labelled_projection"}]}
        hosts = g.build_hosts(hw)
        self.assertIsNone(hosts[0]["measured"])


class MeasuredCellTests(unittest.TestCase):
    def test_none_measured_returns_none(self):
        self.assertIsNone(g.measured_cell(None))
        self.assertIsNone(g.measured_cell({}))

    def test_plain_fields_render(self):
        cell = g.measured_cell({"cpu_brand": "Apple M1", "cores": 3})
        self.assertIn("cpu_brand=Apple M1", cell)
        self.assertIn("cores=3", cell)

    def test_mlx_smoke_renders_compactly(self):
        cell = g.measured_cell({"mlx_smoke": {
            "model": "mlx-community/Qwen2.5-0.5B-Instruct-4bit",
            "revision": "a5339a4131f135d0fdc6a5c8b5bbed2753bbe0f3",
            "tokens_per_second": 146.57, "generation_tokens": 32,
        }})
        self.assertIn("mlx-community/Qwen2.5-0.5B-Instruct-4bit@a5339a4", cell)
        self.assertIn("146.57 tok/s", cell)
        self.assertIn("32 tokens", cell)


class QualifiedModelsRenderTests(unittest.TestCase):
    """render_md() takes a plain dict, so the new section can be tested without touching the
    real repository tree."""

    def _minimal_data(self, qualified_models):
        return {
            "summary": {
                "layers": {"foundation": 0, "us-equities": 0}, "winners": 0, "distinct_components": 0,
                "pins_behind_upstream": [], "e2e_accepted": {p: 0 for p in g.PLATFORMS},
                "needs_host": {p: 0 for p in g.PLATFORMS}, "not_joined_to_manifest": [],
            },
            "setup_order": [], "hosts": [], "layers": [], "qualified_models": qualified_models,
        }

    def test_empty_section_renders_a_placeholder_row(self):
        md = g.render_md(self._minimal_data([]))
        self.assertIn("## Qualified local models", md)
        self.assertIn("| — | — | — | — | — | — | — | — |", md)

    def test_populated_section_renders_every_field(self):
        qm = {
            "catalog": "foundation", "layer_id": "layer-a", "component_id": "vllm", "platform": "linux-wsl2-x86_64",
            "model_id": "Qwen/Qwen3-8B-AWQ", "revision": "abc123", "runtime": "vllm", "runtime_version": "0.9.0",
            "bars": "20/20 tool calls", "result": "pass", "host_id": "widget-20260101",
            "receipt_path": "evidence/hosts/widget-20260101/receipt.json",
        }
        md = g.render_md(self._minimal_data([qm]))
        self.assertIn("Qwen/Qwen3-8B-AWQ", md)
        self.assertIn("abc123", md)
        self.assertIn("vllm", md)
        self.assertIn("0.9.0", md)
        self.assertIn("widget-20260101", md)
        self.assertIn("pass", md)
        self.assertIn("evidence/hosts/widget-20260101/receipt.json", md)

    def test_it_never_claims_acceptance(self):
        md = g.render_md(self._minimal_data([]))
        section = md.split("## Qualified local models", 1)[1].split("## ", 1)[0]
        self.assertIn("never", section)
        self.assertIn("flip rule", section)


class RealRepoQualifiedModelsShapeTests(unittest.TestCase):
    """The real join's qualified_models list is well formed (empty is fine; the fixture-level
    behavior is covered above)."""

    def test_qualified_models_key_is_a_list(self):
        data = g.build()
        self.assertIsInstance(data["qualified_models"], list)


if __name__ == "__main__":
    unittest.main()


class OpenGapCountTests(unittest.TestCase):
    """The grid shows 'executable now / all open' gaps: a layer whose only open gap needs a login,
    hardware or a user decision must not read as having none (readiness audit, 2026-09-23)."""

    def test_execution_broker_shows_its_login_gated_gap(self):
        data = json.loads((ROOT / "catalogs/landscape/new-host-grand-list.json").read_text(encoding="utf-8"))
        layer = next(l for l in data["layers"] if l["layer_id"] == "execution-broker")
        self.assertGreaterEqual(layer["open_gaps"], layer["open_executable_now_gaps"])
        page = (ROOT / "docs/new-host-grand-list.md").read_text(encoding="utf-8")
        self.assertIn("Open gaps (executable now / all)", page)
        self.assertIn(f"{layer['open_executable_now_gaps']} / {layer['open_gaps']} |", page)
