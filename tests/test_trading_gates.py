"""Synthetic fixtures for scripts/trading_gates.py (local integration; no receipts are replayed)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import trading_gates  # noqa: E402


def gate(**overrides):
    base = {
        "id": "g", "rung": "sim", "layer": "backtesting-engine", "title": "t", "status": "established",
        "owner": "this-effort", "evidence_class": "synthetic", "required": True,
        "receipt_path": "r.json", "flip_condition": {"type": "equals", "pointer": "/ok", "equals": True}, "note": "",
    }
    base.update(overrides)
    return base


def document(*gates):
    return {"schema_version": 1, "rungs": ["sim", "paper", "live"], "gates": list(gates)}


class TradingGatesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, relative, payload):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def run_check(self, doc):
        path = self.write("gates.json", doc)
        return trading_gates.check(self.root, path)

    def test_established_gate_with_matching_receipt_passes(self):
        self.write("r.json", {"ok": True})
        result = self.run_check(document(gate()))
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["errors"], [])
        self.assertTrue(result["rung_ready"]["sim"])

    def test_established_gate_with_missing_receipt_fails(self):
        result = self.run_check(document(gate()))
        self.assertEqual(result["status"], "failed")
        self.assertIn("receipt missing", result["errors"][0])

    def test_established_gate_with_false_condition_fails(self):
        self.write("r.json", {"ok": False})
        result = self.run_check(document(gate()))
        self.assertEqual(result["status"], "failed")
        self.assertIn("/ok", result["errors"][0])

    def test_absent_pointer_is_reported_not_crashed(self):
        self.write("r.json", {"other": 1})
        result = self.run_check(document(gate(flip_condition={"type": "equals", "pointer": "/a/b/0", "equals": 1})))
        self.assertEqual(result["status"], "failed")
        self.assertIn("pointer absent", result["errors"][0])

    def test_not_established_gate_whose_receipt_holds_is_a_flip_candidate_not_an_error(self):
        self.write("r.json", {"ok": True})
        result = self.run_check(document(gate(status="not_established")))
        self.assertEqual(result["status"], "passed")
        self.assertEqual([c["id"] for c in result["flip_candidates"]], ["g"])
        self.assertFalse(result["rung_ready"]["sim"])
        self.assertEqual(result["blocking"]["sim"], ["g"])

    def test_array_contains_id_condition(self):
        self.write("stack.json", {"components": [{"id": "exchange-calendars"}, {"id": "duckdb"}]})
        good = gate(receipt_path="stack.json", flip_condition={"type": "array_contains_id", "pointer": "/components", "id": "exchange-calendars"})
        self.assertEqual(self.run_check(document(good))["status"], "passed")
        bad = gate(receipt_path="stack.json", flip_condition={"type": "array_contains_id", "pointer": "/components", "id": "absent"})
        self.assertEqual(self.run_check(document(bad))["status"], "failed")

    def test_exists_condition_accepts_non_json_receipts(self):
        (self.root / "decision.md").write_text("# decision\n", encoding="utf-8")
        result = self.run_check(document(gate(receipt_path="decision.md", flip_condition={"type": "exists"})))
        self.assertEqual(result["status"], "passed")

    def test_rung_readiness_requires_every_earlier_rung(self):
        self.write("r.json", {"ok": True})
        sim = gate(id="sim-gate", rung="sim")
        paper = gate(id="paper-gate", rung="paper", status="not_established")
        live = gate(id="live-go", rung="live", status="user_decision", evidence_class="none", flip_condition=None)
        result = self.run_check(document(sim, paper, live))
        self.assertTrue(result["rung_ready"]["sim"])
        self.assertFalse(result["rung_ready"]["paper"])
        self.assertFalse(result["rung_ready"]["live"])
        self.assertEqual(result["blocking"]["live"], ["paper-gate", "live-go"])

    def test_optional_gates_do_not_block_readiness(self):
        self.write("r.json", {"ok": True})
        result = self.run_check(document(gate(), gate(id="opt", status="paid_entitlement", required=False, evidence_class="none", flip_condition=None)))
        self.assertTrue(result["rung_ready"]["sim"])

    def test_vocabulary_and_shape_errors_are_rejected(self):
        for bad in (
            gate(status="passed"),
            gate(owner="someone"),
            gate(layer="unknown-layer"),
            gate(rung="prod"),
            gate(receipt_path="/abs/path.json"),
            gate(receipt_path="../escape.json"),
            gate(flip_condition={"type": "equals", "pointer": "/ok"}),
            gate(evidence_class="none"),
            {**gate(), "extra": 1},
        ):
            with self.assertRaises(trading_gates.GateError):
                trading_gates.validate_document(document(bad))
        with self.assertRaises(trading_gates.GateError):
            trading_gates.validate_document(document(gate(id="dup"), gate(id="dup")))
        with self.assertRaises(trading_gates.GateError):
            trading_gates.validate_document({"schema_version": 1, "rungs": ["sim"], "gates": [gate()]})

    def test_main_exit_codes(self):
        self.write("r.json", {"ok": True})
        self.write("gates.json", document(gate()))
        self.assertEqual(trading_gates.main(["--root", str(self.root), "--path", "gates.json"]), 0)
        self.write("gates.json", document(gate(status="established", receipt_path="missing.json")))
        self.assertEqual(trading_gates.main(["--root", str(self.root), "--path", "gates.json"]), 1)


class RepositoryGatesTests(unittest.TestCase):
    def test_repository_gate_document_checks_clean(self):
        path = ROOT / trading_gates.GATES
        if not path.exists():
            self.skipTest("gate ladder not yet recorded in this tree")
        result = trading_gates.check(ROOT, path)
        self.assertEqual(result["errors"], [], result["errors"])


if __name__ == "__main__":
    unittest.main()
