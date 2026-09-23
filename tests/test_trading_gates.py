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

    def test_equals_condition_is_type_strict(self):
        # Codex fix-round finding: Python's == treats False == 0 and 0.0 == 0,
        # so an untyped comparison would let a boolean or float receipt value
        # satisfy an integer flip condition (e.g. /unresolved_collisions == 0).
        self.write("r.json", {"ok": False})
        result = self.run_check(document(gate(flip_condition={"type": "equals", "pointer": "/ok", "equals": 0})))
        self.assertEqual(result["status"], "failed")
        holds, _ = trading_gates.condition_holds(self.root, gate(flip_condition={"type": "equals", "pointer": "/ok", "equals": 0}))
        self.assertFalse(holds)

        self.write("r.json", {"ok": 0})
        result = self.run_check(document(gate(status="not_established", flip_condition={"type": "equals", "pointer": "/ok", "equals": 0})))
        self.assertEqual([c["id"] for c in result["flip_candidates"]], ["g"])

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

    def test_exists_condition_rejects_an_empty_file(self):
        # Codex cross-family review of PR-4: presence-only conditions must not be
        # satisfiable by an empty file.
        (self.root / "empty.json").write_text("", encoding="utf-8")
        result = self.run_check(document(gate(receipt_path="empty.json", flip_condition={"type": "exists"})))
        self.assertEqual(result["status"], "failed")
        self.assertIn("empty", result["errors"][0])

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


class GatePointerContentTests(unittest.TestCase):
    """A presence-only ('exists') flip condition is satisfiable by an empty
    placeholder file. Every not-yet-established gate in the repository ladder
    that used to use 'exists' now uses a content condition instead. For each
    of those gates this proves an empty JSON placeholder at the receipt path
    does not make the checker list the gate as a flip candidate, while a
    well-formed passing receipt (matching the schema recorded in the gate's
    own note) does.
    """

    # Gate id -> a well-formed receipt payload that satisfies the gate's
    # current flip_condition, per the schema documented in its note.
    GOOD_RECEIPTS = {
        "dividend-sim-module": {
            "schema_version": 1,
            "status": "closed",
            "mappings_closed": ["market_on_open_proxy", "distributions_and_cash"],
        },
        "pre-2020-delisting": {
            "schema_version": 1,
            "coverage_status": "confirmed",
            "years_covered": [2016, 2017, 2018, 2019],
            "source": {"name": "example-entitled-source", "kind": "entitled"},
        },
        "dated-security-identity": {
            "schema_version": 1,
            "collisions_total": 235,
            "unresolved_collisions": 0,
            "source": "example-entitled-source",
        },
        "pit-news-filings": {
            "schema_version": 1,
            "pit_status": "confirmed",
            "vintage_source": "example-vintage-source",
            "survivorship_free": True,
        },
        "databento-arm-b": {
            "schema_version": 1,
            "arm": "B",
            "provider": "databento",
            "status": "executed",
            "window": {"start": "2016-01-01", "end": "2026-01-01"},
        },
        "native-fault-behaviour": {
            "schema_version": 1,
            "kind": "native_fault_behaviour_receipt",
            "status": "native_faults_passed",
            "broker": "alpaca",
        },
        "ibkr-local-acceptance": {
            "schema_version": 1,
            "kind": "native_ibkr_local_acceptance",
            "status": "passed",
            "broker": "ibkr",
        },
    }

    # Gate id -> a well-formed receipt payload (same shape as GOOD_RECEIPTS)
    # whose terminal value fails the gate's flip condition. Regression for the
    # ibkr-local-acceptance finding: a receipt with the right kind/shape but a
    # failing result must not be a flip candidate.
    BAD_RECEIPTS = {
        "dividend-sim-module": {**GOOD_RECEIPTS["dividend-sim-module"], "status": "open"},
        "pre-2020-delisting": {**GOOD_RECEIPTS["pre-2020-delisting"], "coverage_status": "unconfirmed"},
        "dated-security-identity": {**GOOD_RECEIPTS["dated-security-identity"], "unresolved_collisions": 3},
        "pit-news-filings": {**GOOD_RECEIPTS["pit-news-filings"], "pit_status": "unconfirmed"},
        "databento-arm-b": {**GOOD_RECEIPTS["databento-arm-b"], "status": "not_executed"},
        "native-fault-behaviour": {**GOOD_RECEIPTS["native-fault-behaviour"], "status": "bounded_alpaca_synthetic_cases_passed_native_faults_pending"},
        "ibkr-local-acceptance": {**GOOD_RECEIPTS["ibkr-local-acceptance"], "status": "failed"},
    }

    @classmethod
    def setUpClass(cls):
        path = ROOT / trading_gates.GATES
        if not path.exists():
            raise unittest.SkipTest("gate ladder not yet recorded in this tree")
        cls.gates_by_id = {gate["id"]: gate for gate in trading_gates.load_json(path)["gates"]}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_every_designated_gate_dropped_the_exists_condition(self):
        for gate_id in self.GOOD_RECEIPTS:
            with self.subTest(gate=gate_id):
                condition = self.gates_by_id[gate_id]["flip_condition"]
                self.assertIsNotNone(condition, f"{gate_id}: flip_condition must not be null")
                self.assertNotEqual(condition["type"], "exists",
                                     f"{gate_id}: still uses a presence-only 'exists' condition")

    def test_empty_placeholder_is_not_a_flip_candidate_but_a_passing_receipt_is(self):
        for gate_id, good_content in self.GOOD_RECEIPTS.items():
            with self.subTest(gate=gate_id):
                gate = self.gates_by_id[gate_id]
                self.assertNotEqual(gate["status"], "established", f"{gate_id}: fixture assumes a non-established gate")

                # An empty JSON placeholder (what a presence-only 'exists' flip
                # would have accepted) must not satisfy the content condition.
                self.write(gate["receipt_path"], "{}")
                empty_result = trading_gates.check(self.root, self.write("gates.json", json.dumps(document(gate))))
                self.assertEqual(
                    [c["id"] for c in empty_result["flip_candidates"]], [],
                    f"{gate_id}: empty placeholder was listed as a flip candidate",
                )
                holds, detail = trading_gates.condition_holds(self.root, gate)
                self.assertFalse(holds, f"{gate_id}: empty placeholder unexpectedly holds ({detail})")

                # A well-formed, passing receipt must satisfy the condition
                # and be reported as a flip candidate.
                self.write(gate["receipt_path"], json.dumps(good_content))
                passing_result = trading_gates.check(self.root, self.write("gates.json", json.dumps(document(gate))))
                self.assertEqual(
                    [c["id"] for c in passing_result["flip_candidates"]], [gate_id],
                    f"{gate_id}: well-formed passing receipt was not listed as a flip candidate",
                )
                holds, detail = trading_gates.condition_holds(self.root, gate)
                self.assertTrue(holds, f"{gate_id}: well-formed passing receipt does not hold ({detail})")

    def test_well_formed_failing_receipt_is_not_a_flip_candidate(self):
        for gate_id, bad_content in self.BAD_RECEIPTS.items():
            with self.subTest(gate=gate_id):
                gate = self.gates_by_id[gate_id]
                self.assertNotEqual(gate["status"], "established", f"{gate_id}: fixture assumes a non-established gate")

                self.write(gate["receipt_path"], json.dumps(bad_content))
                result = trading_gates.check(self.root, self.write("gates.json", json.dumps(document(gate))))
                self.assertEqual(
                    [c["id"] for c in result["flip_candidates"]], [],
                    f"{gate_id}: well-formed but failing receipt was listed as a flip candidate",
                )
                holds, detail = trading_gates.condition_holds(self.root, gate)
                self.assertFalse(holds, f"{gate_id}: well-formed failing receipt unexpectedly holds ({detail})")

    def test_no_non_established_gate_in_the_repository_ladder_uses_presence_only_exists(self):
        # Generic guard (not limited to GOOD_RECEIPTS' seven ids): any gate
        # that is not yet established must not rely on a presence-only
        # 'exists' flip condition, which an empty placeholder file satisfies.
        for gate_id, gate in self.gates_by_id.items():
            if gate["status"] == "established":
                continue
            condition = gate["flip_condition"]
            if condition is None:
                continue
            with self.subTest(gate=gate_id):
                self.assertNotEqual(condition["type"], "exists",
                                     f"{gate_id}: non-established gate uses a presence-only 'exists' condition")


if __name__ == "__main__":
    unittest.main()
