"""Authored controls for the pinned LEAN policy; never native acceptance."""
import importlib.util
from decimal import Decimal as D
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/engine-nautilus/spy-parity"


def policy():
    spec = importlib.util.spec_from_file_location("spy_margin_policy_test", SOURCE / "margin_policy.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LeanMarginPolicyTests(unittest.TestCase):
    def test_exact_110_percent_boundary_does_not_call(self):
        p = policy()
        self.assertEqual(p.margin_decision(22, D('10'), D('100'), D('0'), True)['quantity'], 0)
        self.assertFalse(p.margin_decision(20, D('10'), D('100'), D('0'), True)['warning'])

    def test_fee_changes_partial_quantity_without_reversing(self):
        p = policy()
        self.assertEqual(p.margin_decision(23, D('10'), D('100'), D('0'), True)['quantity'], -3)
        self.assertEqual(p.margin_decision(23, D('10'), D('100'), D('1'), True)['quantity'], -4)

    def test_closed_exchange_cannot_execute_liquidation(self):
        d = policy().margin_decision(23, D('10'), D('100'), D('1'), False)
        self.assertEqual(d['quantity'], 0)
        self.assertTrue(d['warning'])

    def test_zero_exposure_and_nonpositive_equity(self):
        p = policy()
        self.assertEqual(p.margin_decision(0, D('10'), D('100'), D('1'), True)['quantity'], 0)
        self.assertEqual(p.margin_decision(23, D('10'), D('0'), D('1'), True)['quantity'], -23)

    def test_warning_boundary_and_execution_stop_are_distinct(self):
        p = policy()
        self.assertTrue(p.margin_decision(20, D('10'), D('105'), D('1'), True)['warning'])
        self.assertEqual(p.margin_decision(20, D('10'), D('105'), D('1'), True)['quantity'], 0)
        self.assertFalse(p.margin_decision(20, D('10'), D('106'), D('1'), True)['warning'])

    def test_invalid_or_fractional_exposure_is_refused(self):
        p = policy()
        for q, price, equity, fee in [(D('2.1'), D('10'), D('100'), D('1')),
                                      (-1, D('10'), D('100'), D('1')),
                                      (23, D('0'), D('100'), D('1')),
                                      (23, D('10'), D('NaN'), D('1'))]:
            with self.subTest(q=q, price=price), self.assertRaises(ValueError):
                p.margin_decision(q, price, equity, fee, True)


class AdaptiveAndSettlementTests(unittest.TestCase):
    def test_intraday_drawdown_cannot_latch_and_close_latches_once(self):
        p = policy()
        state = p.AdaptiveState(D('100'), True)
        self.assertFalse(state.observe(D('95'), completed_close=False, invested=True)['reduce'])
        self.assertTrue(state.observe(D('95'), completed_close=True, invested=True)['reduce'])
        self.assertFalse(state.observe(D('110'), completed_close=True, invested=True)['reduce'])
        self.assertFalse(state.observe(D('90'), completed_close=True, invested=True)['reduce'])

    def test_unsettled_state_cannot_update_peak_or_latch(self):
        s = policy().AdaptiveState(D('100'), True)
        with self.assertRaisesRegex(ValueError, 'unsettled'):
            s.observe(D('120'), completed_close=True, invested=True, settled=False)
        self.assertEqual(s.peak, D('100'))

    def test_observation_retains_original_and_plus_one_native_times(self):
        h = policy().SettlementHandshake()
        self.assertEqual(h.begin(1000, 0), 1001)
        result = h.complete(1001, 0)
        self.assertEqual(result, {'economic_ts_event_ns': 1000, 'observation_ts_event_ns': 1001})

    def test_missing_partial_duplicate_or_early_completion_fails_closed(self):
        p = policy()
        h = p.SettlementHandshake()
        h.begin(1000, 3)
        h.expect_fill('call', -2)
        h.fill('call', -1, 1000)
        with self.assertRaisesRegex(ValueError, 'pending_fill'):
            h.complete(1001, 2)
        h.fill('call', -1, 1000)
        with self.assertRaisesRegex(ValueError, 'observation_time'):
            h.complete(1000, 1)
        self.assertEqual(h.complete(1001, 1)['economic_ts_event_ns'], 1000)
        with self.assertRaisesRegex(ValueError, 'duplicate|missing'):
            h.complete(1001, 1)

    def test_missing_final_completion_is_rejected(self):
        h = policy().SettlementHandshake()
        h.begin(1000, 0)
        with self.assertRaisesRegex(ValueError, 'pending_observation'):
            h.finish()

    def test_unexpected_native_quantity_or_fill_time_is_rejected(self):
        p = policy()
        h = p.SettlementHandshake()
        h.begin(1000, 3)
        h.expect_fill('call', -2)
        with self.assertRaisesRegex(ValueError, 'liquidation_time'):
            h.fill('call', -2, 1001)
        h.fill('call', -2, 1000)
        with self.assertRaisesRegex(ValueError, 'native_quantity'):
            h.complete(1001, 2)


if __name__ == '__main__':
    unittest.main()
