"""Consistency checks for catalogs/landscape/gap-resolution-20260922.json (local integration)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "catalogs/landscape/gap-resolution-20260922.json"
STATUSES = {"settled", "advanced", "not_settled", "open"}
CATEGORIES = {
    "executable_now", "needs_user_login", "needs_paid_entitlement", "needs_hardware", "time_gated",
    "peer_owned", "codex_limited", "manifest_gap", "documentation_fix", "not_actionable", "needs_user_input",
}


class GapResolutionLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(LEDGER.read_text(encoding="utf-8"))

    def test_covers_every_landscape_row(self):
        rows = set()
        for catalog in ("foundation", "us-equities"):
            data = json.loads((ROOT / f"catalogs/landscape/{catalog}.json").read_text(encoding="utf-8"))
            rows |= {(catalog, row["layer_id"]) for row in data["layers"]}
        ledger_rows = {(layer["catalog"], layer["layer_id"]) for layer in self.doc["layers"]}
        self.assertEqual(ledger_rows, rows)

    def test_vocabularies_and_receipt_links(self):
        receipt_paths = {r["path"] for r in self.doc["receipts"]}
        for layer in self.doc["layers"]:
            indexes = [g["index"] for g in layer["gaps"]]
            self.assertEqual(len(indexes), len(set(indexes)), layer["layer_id"])
            for gap in layer["gaps"]:
                with self.subTest(layer=layer["layer_id"], gap=gap["index"]):
                    self.assertIn(gap["status"], STATUSES)
                    self.assertIn(gap["category"], CATEGORIES)
                    self.assertTrue(gap["blocker"].strip())
                    self.assertEqual(gap["status"] == "open", not gap["receipts"])
                    for path in gap["receipts"]:
                        self.assertIn(path, receipt_paths)
                        self.assertTrue((ROOT / path).is_file(), path)

    def test_every_receipt_is_referenced_and_exists(self):
        referenced = {p for layer in self.doc["layers"] for g in layer["gaps"] for p in g["receipts"]}
        for receipt in self.doc["receipts"]:
            with self.subTest(receipt=receipt["path"]):
                self.assertTrue((ROOT / receipt["path"]).is_file())
                if receipt["gap_refs"]:
                    self.assertIn(receipt["path"], referenced)
                else:
                    # Operational receipts (e.g. the Headroom live-store cleanup) settle no gap.
                    self.assertEqual(receipt["settles_gap"], "not_applicable")

    def test_no_host_paths(self):
        text = LEDGER.read_text(encoding="utf-8")
        self.assertNotRegex(text, r"/home/(?!example/)")
        self.assertNotIn("/tmp/claude-", text)

    def test_status_matches_receipts_unless_a_coordinator_note_says_why(self):
        ladder = {True: "settled", "true": "settled", "partially": "advanced", False: "not_settled", "false": "not_settled", "no": "not_settled"}
        by_path = {r["path"]: r for r in self.doc["receipts"]}
        rank = {"not_settled": 0, "advanced": 1, "settled": 2}
        for layer in self.doc["layers"]:
            for gap in layer["gaps"]:
                if not gap["receipts"]:
                    continue
                values = []
                for path in gap["receipts"]:
                    raw = by_path[path]["settles_gap"]
                    key = raw if not isinstance(raw, str) else raw.split(" ")[0].strip().lower()
                    self.assertIn(key, ladder, f"unknown settles_gap {raw!r} in {path}")
                    values.append(ladder[key])
                expected = max(values, key=rank.get)
                with self.subTest(layer=layer["layer_id"], gap=gap["index"]):
                    if gap["status"] != expected:
                        self.assertTrue(gap.get("coordinator_note"), "status differs from receipts without a coordinator note")

    def test_source_text_matches_the_source_revision(self):
        import hashlib
        import subprocess
        rev = self.doc["source_revision"]
        texts = {}
        for rel, digest in self.doc["source_files_sha256"].items():
            try:
                raw = subprocess.run(["git", "-C", str(ROOT), "show", f"{rev}:{rel}"], capture_output=True, check=True).stdout
            except (OSError, subprocess.CalledProcessError):
                self.skipTest(f"{rev} is not in this checkout's history (shallow clone)")
            self.assertEqual(hashlib.sha256(raw).hexdigest(), digest, rel)
            catalog = rel.rsplit("/", 1)[1].removesuffix(".json")
            for row in json.loads(raw)["layers"]:
                texts[(catalog, row["layer_id"])] = row.get("open_gaps", [])
        for layer in self.doc["layers"]:
            source = texts[(layer["catalog"], layer["layer_id"])]
            self.assertEqual([g["index"] for g in layer["gaps"]], list(range(len(source))), layer["layer_id"])
            for gap in layer["gaps"]:
                self.assertEqual(gap["source_text"], source[gap["index"]], (layer["layer_id"], gap["index"]))

    def test_no_host_paths_in_receipts_or_blueprints(self):
        import re
        pattern = re.compile(r"/home/(?!example/)|/tmp/claude-|-home-[a-z]+-code-")
        for base in ("evidence/artifacts/gap-resolution-20260922", "blueprints/gap-resolution-20260922"):
            for path in (ROOT / base).rglob("*"):
                if path.is_file() and path.suffix in {".json", ".sh", ".py", ".md", ".txt"}:
                    with self.subTest(path=str(path.relative_to(ROOT))):
                        self.assertIsNone(pattern.search(path.read_text(encoding="utf-8", errors="replace")))


if __name__ == "__main__":
    unittest.main()
