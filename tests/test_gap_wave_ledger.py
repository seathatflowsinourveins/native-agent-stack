"""Checks for the wave-2 gap ledger (local integration)."""
from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "catalogs/landscape/gap-wave2-20260923--gap-resolution.json"
RANK = {"not_run": 0, "deferred": 1, "covered_elsewhere": 2, "not_settled": 3, "advanced": 4, "settled": 5}


def _tool():
    spec = importlib.util.spec_from_file_location("gap_wave_ledger", ROOT / "tools/sota-convergence/gap_wave_ledger.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GapWaveLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(LEDGER.read_text(encoding="utf-8"))
        cls.tool = _tool()

    def test_ledger_is_up_to_date(self):
        self.assertEqual(self.tool.main(["--root", str(ROOT), "--wave", "gap-wave2-20260923",
                                         "--owner", "gap-resolution", "--check"]), 0)

    def test_status_is_the_best_credit_and_multi_gap_receipts_never_settle(self):
        receipts = {r["path"]: r for r in self.doc["receipts"]}
        for layer in self.doc["layers"]:
            for gap in layer["gaps"]:
                with self.subTest(layer=layer["layer_id"], gap=gap["index"]):
                    credits = []
                    for entry in gap["receipts"]:
                        receipt = receipts[entry["path"]]
                        override = (receipt.get("per_gap_settles") or {}).get(f"{layer['layer_id']}:{gap['index']}")
                        if override:
                            base = {"true": "settled", "partially": "advanced", "false": "not_settled"}[override]
                            if len(receipt["gap_refs"]) > 1 and base == "settled":
                                base = "advanced"
                            self.assertEqual(entry["credit"], base)
                        self.assertTrue((ROOT / entry["path"]).is_file())
                        self.assertIn([layer["layer_id"], gap["index"]], receipt["gap_refs"])
                        if len(receipt["gap_refs"]) > 1:
                            self.assertNotEqual(entry["credit"], "settled")
                        credits.append(entry["credit"])
                    expected = max(credits, key=RANK.get) if credits else "not_run"
                    self.assertEqual(gap["status"], expected)

    def test_settle_key_rejects_unknown_values(self):
        self.assertEqual(self.tool.settle_key("partially (was true)"), "partially")
        self.assertEqual(self.tool.settle_key(True), "true")
        with self.assertRaises(SystemExit):
            self.tool.settle_key("maybe")

    def test_catalog_layer_dir_style_reads_prefixed_dirs_and_defaults_the_layer(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "evidence/artifacts/wave-x"
            (base / "foundation__native-clients").mkdir(parents=True)
            (base / "native-clients").mkdir()
            receipt = {"id": "r1", "source_revision": "92bb279", "gap_refs": [{"gap_index": 2}, 5],
                       "settles_gap": "partially", "verdict_impact": {"direction": "inconclusive"}}
            (base / "foundation__native-clients/r1.json").write_text(json.dumps(receipt))
            (base / "foundation__native-clients/results.json").write_text(json.dumps({"gap_refs": "not a receipt"}))
            (base / "native-clients/r2.json").write_text(json.dumps({**receipt, "id": "r2",
                                                                      "gap_refs": [{"layer_id": "native-clients", "gap_index": 0}]}))
            prefixed = self.tool.load_receipts(Path(tmp), "wave-x", "catalog__layer")
            self.assertEqual([r["id"] for r in prefixed], ["r1"])
            self.assertEqual(prefixed[0]["gap_refs"], [["native-clients", 2], ["native-clients", 5]])
            plain = self.tool.load_receipts(Path(tmp), "wave-x", "layer")
            self.assertEqual([r["id"] for r in plain], ["r2"])

    def test_catalog_layer_accepts_outcome_only_receipts_and_rejects_non_receipts(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            layer = Path(tmp) / "evidence/artifacts/wave-y/foundation__workers"
            (layer / "raw").mkdir(parents=True)
            (layer / "raw/stdout.json").write_text("{}")  # subdirectories are never read
            (layer / "results.json").write_text(json.dumps({"0": "advanced"}))
            (layer / "_index.json").write_text("{}")
            (layer / "preregistrations-fixround.json").write_text("{}")
            shapes = {"a": {"gap_index": 0, "outcome": "advanced"},
                      "b": {"gap_index": 3, "outcome": "deferred", "blocker": "needs the user"},
                      "c": {"gap_index": 4, "outcome": "covered_elsewhere"},
                      "d": {"gap_index": 5, "outcome": "settled"}}
            for name, body in shapes.items():
                (layer / f"{name}.json").write_text(json.dumps({"id": name, **body}))
            loaded = {r["id"]: r for r in self.tool.load_receipts(Path(tmp), "wave-y", "catalog__layer")}
            self.assertEqual(sorted(loaded), ["a", "b", "c", "d"])
            self.assertEqual(loaded["a"]["gap_refs"], [["workers", 0]])
            self.assertEqual(self.tool.SETTLES[loaded["a"]["settles_key"]], "advanced")
            self.assertEqual(self.tool.SETTLES[loaded["b"]["settles_key"]], "deferred")
            self.assertEqual(self.tool.SETTLES[loaded["c"]["settles_key"]], "covered_elsewhere")
            self.assertEqual(self.tool.SETTLES[loaded["d"]["settles_key"]], "settled")
            self.assertIsNone(loaded["a"]["source_revision"])  # build() defaults and flags it
            (layer / "stray.json").write_text(json.dumps({"note": "not a receipt"}))
            with self.assertRaises(SystemExit) as raised:
                self.tool.load_receipts(Path(tmp), "wave-y", "catalog__layer")
            self.assertIn("stray.json", str(raised.exception.code))
            (layer / "stray.json").write_text(json.dumps({"gap_index": 1, "outcome": "maybe"}))
            with self.assertRaises(SystemExit):
                self.tool.load_receipts(Path(tmp), "wave-y", "catalog__layer")

    def test_rank_keeps_deferral_below_any_executed_outcome(self):
        rank = self.tool.RANK
        self.assertLess(rank["not_run"], rank["deferred"])
        self.assertLess(rank["deferred"], rank["not_settled"])
        self.assertLess(rank["covered_elsewhere"], rank["not_settled"])

    def test_every_receipt_names_the_crosswalk_revision(self):
        for receipt in self.doc["receipts"]:
            self.assertTrue(self.doc["source_revision"].startswith(receipt["source_revision"][:7]), receipt["path"])

    def test_repo_raw_artifacts_match_their_recorded_hash(self):
        import hashlib
        for path in sorted((ROOT / "evidence/artifacts/gap-wave2-20260923").rglob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            for artifact in data.get("raw_artifacts") or []:
                if not isinstance(artifact, dict) or not artifact.get("sha256"):
                    continue
                rel = artifact.get("path", "")
                if rel.startswith(("~", "/", "<")) or not (ROOT / rel).is_file():
                    continue  # host-side or scratch artifact, recorded by hash only
                with self.subTest(receipt=path.name, artifact=rel):
                    actual = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
                    self.assertEqual(actual, artifact.get("published_sha256", artifact["sha256"]))

    def test_no_host_paths_or_session_identifiers(self):
        text = LEDGER.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"/home/(?!example/)|/tmp/claude-|[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", text))


if __name__ == "__main__":
    unittest.main()
