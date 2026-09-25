"""Hermetic checks for the hftbacktest L1 feasibility fixture.

This is OUR integration check (docs/acceptance-evidence-policy.md), not an
upstream test. It skips cleanly if `hftbacktest` is not importable on the
running interpreter -- it is a pinned dependency installed into an isolated
venv (~/.local/share/native-agent-stack/hftbacktest-2.4.4), not into the
repository's own CI Python, so a skip here is expected on hosts that have not
set up that venv.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
BLUEPRINT = HERE.parent

try:
    import hftbacktest  # noqa: F401
    HFTBACKTEST_AVAILABLE = True
except ImportError:
    HFTBACKTEST_AVAILABLE = False


def _load_feasibility_module():
    spec = importlib.util.spec_from_file_location(
        "l1_feasibility", BLUEPRINT / "l1_feasibility.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(HFTBACKTEST_AVAILABLE, "hftbacktest is not installed on this interpreter")
class L1FeasibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_feasibility_module()

    def test_marketable_ioc_fills_from_l1_depth_alone(self):
        import hftbacktest.order as order_mod

        result = self.mod.run_ioc_scenario(self.mod.build_scenario_a, submit_at_ns=1 * self.mod.NS)
        self.assertEqual(result["order_status"], order_mod.FILLED)
        self.assertAlmostEqual(result["exec_price"], 10.02, places=6)
        self.assertAlmostEqual(result["exec_qty"], 10.0, places=6)
        self.assertAlmostEqual(result["leaves_qty"], 0.0, places=6)

    def test_ioc_expires_when_touch_moves_away_before_arrival(self):
        import hftbacktest.order as order_mod

        result = self.mod.run_ioc_scenario(self.mod.build_scenario_b, submit_at_ns=50 * self.mod.MS)
        self.assertEqual(result["order_status"], order_mod.EXPIRED)
        self.assertAlmostEqual(result["exec_qty"], 0.0, places=6)
        self.assertAlmostEqual(result["leaves_qty"], 10.0, places=6)

    def test_queue_trade_depletion_requires_an_aggressor_side(self):
        import hftbacktest.order as order_mod

        result = self.mod.run_scenario_c()
        self.assertEqual(result["with_side"]["order_status"], order_mod.FILLED)
        self.assertEqual(result["without_side"]["order_status"], order_mod.NEW)
        self.assertGreater(result["with_side"]["exec_qty"], 0.0)
        self.assertAlmostEqual(result["without_side"]["exec_qty"], 0.0, places=6)

    def test_feasibility_script_runs_end_to_end_and_matches_expectations(self):
        # Runs the script's own __main__ path via subprocess-free module import so any
        # regression in wiring (imports, argparse, JSON shape) is caught, not just the
        # underlying functions exercised in the tests above.
        import subprocess

        proc = subprocess.run(
            [sys.executable, str(BLUEPRINT / "l1_feasibility.py")],
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(
            out["scenario_a_marketable_ioc_fill_from_l1_depth"]["order_status_name"], "FILLED"
        )
        self.assertEqual(
            out["scenario_b_ioc_expiry_from_l1_depth"]["order_status_name"], "EXPIRED"
        )
        self.assertEqual(
            out["scenario_c_queue_trade_depletion_needs_side"]["with_side"]["order_status_name"],
            "FILLED",
        )
        self.assertEqual(
            out["scenario_c_queue_trade_depletion_needs_side"]["without_side"]["order_status_name"],
            "NEW",
        )


class LockfileAndReceiptStructureTests(unittest.TestCase):
    """These run regardless of whether hftbacktest is installed -- they check
    checked-in artifacts, not native execution."""

    def test_requirements_lock_pins_hftbacktest_2_4_4_with_hashes(self):
        lock_text = (BLUEPRINT / "requirements.lock").read_text(encoding="utf-8")
        self.assertIn("hftbacktest==2.4.4", lock_text)
        self.assertIn("--hash=sha256:", lock_text)

    def test_receipt_is_valid_json_with_required_top_level_keys(self):
        receipt_path = BLUEPRINT / "receipt.json"
        self.assertTrue(receipt_path.is_file(), receipt_path)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        for key in ("evidence", "versions", "l1_feasibility_verdict", "unverified"):
            self.assertIn(key, receipt)


if __name__ == "__main__":
    unittest.main()
