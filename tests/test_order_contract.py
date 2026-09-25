"""Behavior checks for the broker-disconnected basic intent boundary."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from decimal import Decimal, localcontext

PATH = Path(__file__).resolve().parents[1] / "blueprints/us-equities/order-contract/order_contract.py"
SPEC = importlib.util.spec_from_file_location("order_contract", PATH)
contract = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contract)


class OrderContractTests(unittest.TestCase):
    def intent(self, **changes):
        return dict(symbol="SPY", qty="2", side="buy", type="limit",
                    time_in_force="day", limit_price="100.10",
                    client_order_id="offline-example-001", **changes)

    def check_reject(self, field, value):
        intent = self.intent()
        intent[field] = value
        with self.assertRaises(contract.ContractError):
            contract.canonicalize(intent)

    def test_exact_canonical_payload_and_defaults(self):
        before = self.intent()
        result = contract.canonicalize(before)
        self.assertEqual(result["mode"], "offline")
        self.assertFalse(result["submission_enabled"])
        self.assertEqual(result["intent"]["limit_price"], "100.1")
        self.assertEqual(result["intent"]["qty"], "2")
        self.assertEqual(result["intent"]["order_class"], "simple")
        self.assertIs(result["intent"]["extended_hours"], False)
        self.assertEqual(before, self.intent())
        self.assertEqual(contract.dumps(before), contract.dumps(dict(reversed(list(before.items())))))

    def test_market_excludes_limit_and_preserves_sell(self):
        intent = self.intent()
        intent.update(type="market", side="sell")
        del intent["limit_price"]
        self.assertEqual(contract.canonicalize(intent)["intent"]["side"], "sell")
        intent["limit_price"] = "1"
        with self.assertRaises(contract.ContractError):
            contract.canonicalize(intent)

    def test_unknown_advanced_transport_and_nested_fields_rejected(self):
        for key in ("advanced_instructions", "algorithm", "destination", "notional",
                    "take_profit", "stop_loss", "legs", "position_intent", "endpoint",
                    "paper", "live", "account_id", "submit", "operation", "typo"):
            with self.subTest(key=key):
                self.check_reject(key, {"algorithm": "VWAP"})

    def test_finite_exact_numbers_only(self):
        for field in ("qty", "limit_price"):
            for value in (True, False, 1.0, float("nan"), float("inf"), None, [], {},
                          "NaN", "Infinity", "-1", "0", " 1", "1 ", "+1", "1e2",
                          "1_000", "１", "1\n", "1" * 25, Decimal("Infinity"), Decimal("NaN")):
                with self.subTest(field=field, value=repr(value)):
                    self.check_reject(field, value)

    def test_local_bounds_whole_shares_and_price_increments(self):
        for qty in ("0.1", "1.01", "1000000001", 10**100):
            self.check_reject("qty", qty)
        for price in ("1.001", "0.00001", "1000000000.01"):
            self.check_reject("limit_price", price)
        for price in ("0.0001", "0.9999", "1.00", "999999999.99"):
            intent = self.intent()
            intent["limit_price"] = price
            with localcontext() as ctx:
                ctx.prec = 2
                self.assertEqual(Decimal(contract.canonicalize(intent)["intent"]["limit_price"]), Decimal(price))

    def test_exact_decimal_and_integer_input(self):
        intent = self.intent()
        intent.update(qty=3, limit_price=Decimal("123.4500"))
        self.assertEqual(contract.canonicalize(intent)["intent"]["limit_price"], "123.45")
        intent["limit_price"] = Decimal("1e1000000")
        with self.assertRaises(contract.ContractError):
            contract.canonicalize(intent)

    def test_schema_and_local_symbol_id_policy(self):
        for value in (None, [], "SPY", 42):
            with self.assertRaises(contract.ContractError):
                contract.canonicalize(value)
        for field, values in {"symbol": ("spy", "AAPL/US", "SPY\n", "", 3),
                              "client_order_id": ("", "x" * 129, "id\n", "id space", None),
                              "type": ("stop", [], None), "side": ("BUY", [], None),
                              "time_in_force": ("gtc", None), "order_class": ("bracket", "", None),
                              "extended_hours": (True, 0, "false", None)}.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    self.check_reject(field, value)
        intent = self.intent()
        intent["symbol"] = "BRK.B"
        self.assertEqual(contract.canonicalize(intent)["intent"]["symbol"], "BRK.B")
        for field in self.intent():
            missing = self.intent()
            del missing[field]
            with self.subTest(missing=field), self.assertRaises(contract.ContractError):
                contract.canonicalize(missing)

    def test_json_boundary_rejects_duplicates_excess_size_and_nonfinite(self):
        for text in ('{"qty":"1","qty":"2"}', '{"qty":NaN}', '[' * 1100,
                     '{"qty":1e999999999999999999999999999999}', '{"qty":1e2}',
                     'x' * (contract.MAX_JSON_BYTES + 1)):
            with self.assertRaises(contract.ContractError):
                contract.loads(text)
        text = json.dumps(self.intent()).replace('"100.10"', '100.10')
        self.assertEqual(contract.loads(text)["intent"]["limit_price"], "100.1")

    def test_build_envelope_defaults_equal_canonicalize(self):
        for changes in ({}, {"side": "sell"}, {"limit_price": "0.1234"}, {"symbol": "BRK.B"}):
            intent = dict(self.intent(), **changes)
            with self.subTest(changes=changes):
                self.assertEqual(contract.build_envelope(intent), contract.canonicalize(intent))
        for field, value in (("qty", "0.5"), ("extended_hours", True), ("limit_price", "1.001")):
            with self.subTest(field=field), self.assertRaises(contract.ContractError):
                contract.build_envelope(dict(self.intent(), **{field: value}))

    def test_build_envelope_adapter_policies_are_explicit_and_narrow(self):
        sell = dict(self.intent(), side="sell", qty="0.123456789")
        result = contract.build_envelope(sell, fractional_sell_qty=True)
        self.assertEqual((result["mode"], result["submission_enabled"]), ("offline", False))
        self.assertEqual(result["intent"]["qty"], "0.123456789")
        self.assertEqual(contract.build_envelope(dict(sell, qty=Decimal("0.500000000")),
                                                 fractional_sell_qty=True)["intent"]["qty"], "0.5")
        for changes in ({"side": "buy"}, {"qty": "0.1234567891"}, {"qty": "1e-9"}, {"qty": 0.5},
                        {"qty": Decimal("1E-10")}):
            with self.subTest(changes=repr(changes)), self.assertRaises(contract.ContractError):
                contract.build_envelope(dict(sell, **changes), fractional_sell_qty=True)
        with self.assertRaises(contract.ContractError):
            contract.build_envelope(sell)  # whole shares unless the adapter opts in
        extended = dict(self.intent(), extended_hours=True)
        self.assertIs(contract.build_envelope(extended, extended_hours_allowed=True)["intent"]["extended_hours"], True)
        for value in (1, "true", None):
            with self.subTest(extended_hours=value), self.assertRaises(contract.ContractError):
                contract.build_envelope(dict(extended, extended_hours=value), extended_hours_allowed=True)
        with self.assertRaises(contract.ContractError):  # policies never relax the price increment
            contract.build_envelope(dict(sell, limit_price="100.001"), fractional_sell_qty=True,
                                    extended_hours_allowed=True)

    def test_cli_rejects_submission_and_reports_no_values(self):
        result = subprocess.run([sys.executable, str(PATH), "--submit"],
                                input=json.dumps(self.intent()), text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        result = subprocess.run([sys.executable, str(PATH)], input=json.dumps(self.intent()),
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)["submission_enabled"])
        secret = "synthetic-unknown-value"
        result = subprocess.run([sys.executable, str(PATH)],
                                input=json.dumps(self.intent(unknown=secret)), text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn(secret, result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
