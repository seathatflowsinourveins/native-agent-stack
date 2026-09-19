import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "alpaca_capabilities", Path(__file__).resolve().parents[1]
    / "blueprints/us-equities/architecture/alpaca_capabilities.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InstructionPreservation(unittest.TestCase):
    def test_missing_instructions_fail_closed(self):
        self.assertFalse(module.preserved({"algorithm": "DMA"}, {"symbol": "SPY"}))

    def test_changed_or_partial_instructions_fail_closed(self):
        expected = {"algorithm": "DMA", "destination": "NYSE"}
        for actual in ({"algorithm": "DMA"}, {"algorithm": "DMA", "destination": "ARCA"}, None):
            self.assertFalse(module.preserved(expected, {"advanced_instructions": actual}))

    def test_exact_instructions_preserved(self):
        expected = {"algorithm": "DMA", "destination": "NYSE"}
        self.assertTrue(module.preserved(expected, {"advanced_instructions": dict(expected)}))
