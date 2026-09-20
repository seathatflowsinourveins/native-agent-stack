"""Failure checks for the offline Nautilus report verifier; no engine install or run."""

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/verify_nautilus_ci.py"
UUID_A = "e16a9b55-7d11-43ed-877a-91840b37044c"
UUID_B = "d82634b6-df9b-4043-aaf4-cc3a9e2d4795"


class NativeNautilusCITests(unittest.TestCase):
    def verifier(self):
        self.assertTrue(SCRIPT.is_file(), "The offline CI verifier is missing")
        spec = importlib.util.spec_from_file_location("verify_nautilus_ci", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def reports(self):
        account = [{"total": "1000000.00", "currency": "USD"},
                   {"total": "1000431.00", "currency": "USD"}]
        fills = [{"status": "FILLED", "commissions": "['0.00 USD']", "filled_qty": "100000",
                  "avg_px": "1.00000", "side": "BUY"},
                 {"status": "FILLED", "commissions": "['0.00 USD']", "filled_qty": "100000",
                  "avg_px": "1.00431", "side": "SELL"}]
        positions = [{"realized_pnl": "431.00 USD", "side": "FLAT", "quantity": "0"}]
        return account, fills, positions

    def proof(self):
        return {"network_namespace": "net:[2]", "interfaces": [[1, "lo"]], "home_exists": False,
                "environment_names": ["HOME", "LANG", "PATH", "PYTHONDONTWRITEBYTECODE",
                                      "PYTHONHASHSEED", "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS"]}

    def test_uuid_normalization_preserves_every_other_report_field(self):
        verifier = self.verifier()
        left = [{"init_id": UUID_A, "avg_px": "1.00", "ts_init": "1704068340000000000"}]
        right = [{"init_id": UUID_B, "avg_px": "1.00", "ts_init": "1704068340000000000"}]
        self.assertEqual(verifier.normalize_rows("fills.csv", left), verifier.normalize_rows("fills.csv", right))
        self.assertEqual(left[0]["init_id"], UUID_A, "Raw report rows must remain available")
        right[0]["avg_px"] = "1.01"
        self.assertNotEqual(verifier.normalize_rows("fills.csv", left), verifier.normalize_rows("fills.csv", right))
        with self.assertRaisesRegex(ValueError, "UUIDv4"):
            verifier.normalize_rows("fills.csv", [{"init_id": UUID_A.replace("43ed", "13ed")}])

    def test_position_normalization_is_limited_to_suffix_and_event_identity(self):
        verifier = self.verifier()
        left = [{"position_id": "EUR/USD.SIM-EMACross-000-" + UUID_A,
                 "events": repr([{"event_id": UUID_A, "last_px": "1.00", "ts_event": 123}])}]
        right = [{"position_id": "EUR/USD.SIM-EMACross-000-" + UUID_B,
                  "events": repr([{"event_id": UUID_B, "last_px": "1.00", "ts_event": 123}])}]
        self.assertEqual(verifier.normalize_rows("positions.csv", left), verifier.normalize_rows("positions.csv", right))
        right[0]["events"] = repr([{"event_id": UUID_B, "last_px": "1.00", "ts_event": 124}])
        self.assertNotEqual(verifier.normalize_rows("positions.csv", left), verifier.normalize_rows("positions.csv", right))
        with self.assertRaisesRegex(ValueError, "UUIDv4"):
            verifier.normalize_rows("positions.csv", [{"position_id": "stable", "events": "[{'event_id': 'not-a-uuid'}]"}])

    def test_independent_decimal_reconciliation_and_flat_position_check(self):
        verifier = self.verifier()
        account, fills, positions = self.reports()
        result = verifier.reconcile_reports(account, fills, positions)
        self.assertEqual(result["realized_pnl_usd"], "431.00")
        self.assertEqual(result["ending_cash_usd"], "1000431.00000")
        for changed, message in (("cash", "cash"), ("position", "flat"), ("side", "side"), ("commission", "commission")):
            with self.subTest(changed=changed):
                a, f, p = copy.deepcopy((account, fills, positions))
                if changed == "cash": a[-1]["total"] = "1000432.00"
                if changed == "position": p[0]["quantity"] = "1"
                if changed == "side": f[0]["side"] = "UNKNOWN"
                if changed == "commission": f[0]["commissions"] = "['1.00 USD']"
                with self.assertRaisesRegex(ValueError, message):
                    verifier.reconcile_reports(a, f, p)

    def test_isolation_cannot_fall_back_to_host_network_or_environment(self):
        verifier = self.verifier()
        verifier.check_isolation(self.proof(), "net:[1]")
        for field, value in (("network_namespace", "net:[1]"), ("interfaces", [[1, "lo"], [2, "eth0"]]),
                             ("home_exists", True), ("environment_names", ["HOME", "BROKER_KEY"])):
            with self.subTest(field=field):
                proof = self.proof()
                proof[field] = value
                with self.assertRaises(ValueError):
                    verifier.check_isolation(proof, "net:[1]")

    def test_failed_verification_retains_machine_readable_failure(self):
        verifier = self.verifier()
        with tempfile.TemporaryDirectory() as directory:
            result = verifier.main(["--output", directory])
            self.assertEqual(result, 1)
            receipt = json.loads((Path(directory) / "verification.json").read_text())
            self.assertEqual(receipt["status"], "failed")
            self.assertTrue(receipt["error"])
            self.assertFalse(receipt["native_acceptance"])


if __name__ == "__main__":
    unittest.main()
