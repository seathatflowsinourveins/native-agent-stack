"""Tests for scripts/new_host_grand_list.py: the join covers every matrix
winner, the per-platform bootstrap-pin flags follow the pin files, projected
tier strings reduce to their result, and the checked-in outputs are fresh."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import hardware_profile as hp
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

    def test_trailing_parenthetical_note_containing_equals_is_dropped(self):
        # catalog PR #125's wsl-workstation-128gb-projected workflow_concurrency_cap:
        # a second '=' inside a trailing explanatory note previously made rsplit("=", 1)
        # return "60)" (the tail of the note) instead of the actual result "16".
        self.assertEqual(
            g.tier_value("min(16, 60 - 2) = 16 (nproc inside WSL is the .wslconfig processors=60)"),
            "16")

    def test_multiple_equals_with_no_trailing_note_still_takes_the_last(self):
        # Unchanged behavior: a string with several '=' but no trailing "(...)" note takes
        # the result after the *last* one, as it always has.
        self.assertEqual(
            g.tier_value("max(6, round(99*0.25,1)=24.8), min(24.8, 32) = 24.8"), "24.8")

    def test_trailing_parens_glued_to_a_token_are_part_of_the_result_not_a_note(self):
        # "min(16, 30)" is glued directly onto its own text with no space before "(", so it
        # is the result itself, not a separate explanatory note to drop -- unlike a genuine
        # trailing note, which is always set off by a space (the case above).
        self.assertEqual(g.tier_value("cap = min(16, 30)"), "min(16, 30)")
        # And the two combine correctly: a real trailing note after a parenthesized result.
        self.assertEqual(g.tier_value("cap = min(16, 30) (a trailing note)"), "min(16, 30)")


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

    def test_every_winner_carries_its_ledger_basis(self):
        ledgers = {c: {l["layer_id"]: l for l in json.loads((REPO_ROOT / rel).read_text(encoding="utf-8"))["layers"]}
                   for c, rel in g.LEDGERS.items()}
        for layer in self.data["layers"]:
            recorded = {w["component_id"]: w for w in ledgers[layer["catalog"]][layer["layer_id"]].get("winners") or []}
            for w in layer["winners"]:
                self.assertIn(w["component_id"], recorded, (layer["layer_id"], w["component_id"]))
                src = recorded[w["component_id"]]
                self.assertEqual(w["why_selected"], src.get("why_selected"), (layer["layer_id"], w["component_id"]))
                self.assertEqual(w["evidence_refs"], list(src.get("evidence_refs") or []), (layer["layer_id"], w["component_id"]))

    def test_rendered_markdown_explains_what_a_winner_means_without_new_paths(self):
        md = g.render_md(self.data)
        section = md.split("## What a winner means", 1)[1].split("\n## ", 1)[0]
        self.assertIn("not a claim that the component is the best in its field", section)
        counts = [int(n) for n in re.findall(r"`[a-z_]+` (\d+)", section)]
        self.assertEqual(sum(counts), len(self.data["layers"]))
        # The Markdown is a new-host document (scripts/release_due.py), so the section names no repository paths.
        self.assertIsNone(re.search(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+", section))

    def test_headline_pairs_add_up_to_the_winners(self):
        # needs_host excludes both accepted and host_verified, so the three counts partition the pairs.
        s = self.data["summary"]
        for p in g.PLATFORMS:
            self.assertEqual(s["e2e_accepted"][p] + s["e2e_host_verified"][p] + s["needs_host"][p], s["winners"], p)

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

    def test_measured_is_read_from_the_evidence_file_when_the_entry_has_none(self):
        # Mirrors exactly what scripts/hardware_profile.py --record-host produces: a
        # native_proven entry with no inline `measured`, only an `evidence` .json path.
        # Previously only the entry's own (absent) `measured` was read, so a --record-host
        # host's real measurements never reached the grand list.
        hw = {"hosts": [{
            "id": "this-host-20260923", "label": "measured host", "evidence_class": "native_proven",
            "evidence": "evidence/artifacts/sota-refresh-20260923/hw-profiles/this-host.json",
        }]}
        hosts = g.build_hosts(hw)
        self.assertIsNotNone(hosts[0]["measured"])
        self.assertIn("cores", hosts[0]["measured"])

    def test_entrys_own_measured_wins_over_the_evidence_files(self):
        hw = {"hosts": [{
            "id": "this-host-20260923", "label": "measured host", "evidence_class": "native_proven",
            "evidence": "evidence/artifacts/sota-refresh-20260923/hw-profiles/this-host.json",
            "measured": {"cores": 999},
        }]}
        hosts = g.build_hosts(hw)
        self.assertEqual(hosts[0]["measured"]["cores"], 999)


class RecordHostToGrandListTests(unittest.TestCase):
    """End to end: scripts/hardware_profile.py --record-host writes a hosts[] entry with no
    inline `measured`; scripts/new_host_grand_list.py's join must still surface non-null
    measured values for it (Codex review finding against 48471ea)."""

    def test_recorded_host_gets_non_null_measured_in_the_grand_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "adoption").mkdir(parents=True)
            (root / "adoption" / "hardware-profiles.json").write_text(
                json.dumps({"hosts": []}), encoding="utf-8")
            (root / "manifests").mkdir()
            (root / "manifests" / "evidence.json").write_text(
                json.dumps({"schema_version": 1, "files": []}), encoding="utf-8")

            patched_report = {
                "schema": "hardware-profile-report-v1", "profiles_source": "adoption/hardware-profiles.json",
                "measured": {"cores": 12, "effective_ram_gb": 64.0, "evidence_class": "native_proven"},
                "recommended": {"workflow_concurrency_cap": 10}, "limits": [],
            }
            with mock.patch.object(hp, "build_report", return_value=patched_report):
                exit_code = hp.cmd_record_host(
                    argparse.Namespace(record_host="recorded-host-20260101", label=None, root=root))
            self.assertEqual(exit_code, 0)

            hw = json.loads((root / "adoption" / "hardware-profiles.json").read_text(encoding="utf-8"))
            with mock.patch.object(g, "ROOT", root):
                hosts = g.build_hosts(hw)
            entry = next(h for h in hosts if h["id"] == "recorded-host-20260101")
            self.assertIsNotNone(entry["measured"])
            self.assertEqual(entry["measured"]["cores"], 12)
            self.assertEqual(entry["measured"]["effective_ram_gb"], 64.0)

    def test_recorded_host_under_a_two_letter_user_name(self):
        # The same round trip under a two-letter account name inside the id ("ed" in
        # "recorded"): matched as a substring, the id was refused, which CI (user "runner")
        # never saw.
        with mock.patch.dict(os.environ, {"USER": "ed", "LOGNAME": "ed"}):
            self.test_recorded_host_gets_non_null_measured_in_the_grand_list()


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
                "e2e_host_verified": {p: 0 for p in g.PLATFORMS},
                "needs_host": {p: 0 for p in g.PLATFORMS}, "not_joined_to_manifest": [],
            },
            "setup_order": [], "hosts": [], "layers": [], "qualified_models": qualified_models,
        }

    def test_headline_counts_host_verified_pairs_as_accepted(self):
        data = self._minimal_data([])
        data["summary"]["e2e_accepted"] = {"linux-wsl2-x86_64": 28, "macos-arm64": 0}
        data["summary"]["e2e_host_verified"] = {"linux-wsl2-x86_64": 18, "macos-arm64": 6}
        md = g.render_md(data)
        self.assertIn("Pairs accepted end to end: 46 (18 of them `host_verified` on a host receipt) on WSL2, "
                      "6 (6 of them `host_verified` on a host receipt) on macOS.", md)

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
