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


if __name__ == "__main__":
    unittest.main()
