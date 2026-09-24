"""Execution prices from rounded cumulative averages (fills.py); stdlib only, no Nautilus."""
from decimal import Decimal as D, localcontext
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "blueprints/us-equities/adaptive-paper/fills.py"
SPEC = importlib.util.spec_from_file_location("adaptive_paper_fills", FILE)
f = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = f
SPEC.loader.exec_module(f)

CENT, FOUR = D("0.01"), D("0.0001")


def resolve(prior_qty, prior_notional, filled, avg, tick, **event):
    return f.resolve_execution(D(prior_qty), D(prior_notional), D(filled), D(avg), tick, **event)


class ReportUnitTests(unittest.TestCase):
    def test_unit_is_the_six_decimal_report_or_finer_never_the_normalized_string(self):
        # The transport drops trailing zeros, so "15" may have been 15.000000.
        for text in ("15", "15.0", "1E+1", "15.000833", "2.77"):
            self.assertEqual(f.report_unit(D(text)), D("0.000001"), text)
        self.assertEqual(f.report_unit(D("15.000833333")), D("0.000000001"))


class ResolveExecutionTests(unittest.TestCase):
    def test_the_paper_grml_exit_resolves_each_share_at_15_01(self):
        # mover-mac-20260924a: 11 x 15.00, then 1 and 1 x 15.01, reported 15.000833 and 15.001538.
        self.assertEqual(resolve(11, "165", 12, "15.000833", FOUR), (D("15.0100"), D("180.0100")))
        self.assertEqual(resolve(12, "180.01", 13, "15.001538", FOUR), (D("15.0100"), D("195.0200")))

    def test_an_execution_event_supplies_the_price(self):
        self.assertEqual(resolve(11, "165", 12, "15.000833", FOUR, event_qty="1", event_price="15.01"),
                         (D("15.0100"), D("180.01")))
        # An event for different shares is not this observation's price: resolved from the report.
        self.assertEqual(resolve(11, "165", 12, "15.000833", FOUR, event_qty="2", event_price="15.01"),
                         (D("15.0100"), D("180.0100")))

    def test_a_contradictory_or_off_grid_event_is_never_replaced_by_a_derived_price(self):
        with self.assertRaisesRegex(ValueError, "fill_event_price_requires_reconciliation"):
            resolve(11, "165", 12, "15.000833", FOUR, event_qty="1", event_price="15.02")
        with self.assertRaisesRegex(ValueError, "fill_event_price_requires_reconciliation"):
            resolve(1999, "29985", 2000, "15.000004", CENT, event_qty="1", event_price="15.009")

    def test_clean_fills_resolve_up_to_the_engines_share_cap(self):
        for qty in (1, 71, 100):
            with self.subTest(qty=qty):
                notional = D("2.77") * qty
                self.assertEqual(resolve(0, "0", qty, "2.77", FOUR), (D("2.7700"), notional))
        self.assertEqual(resolve(0, "0", 3, "100.01", CENT), (D("100.01"), D("300.03")))
        # 5,999 x 15.00 then 1 x 15.01 reports 15.000002: within 6,000 x 0.000001 of the derived
        # 15.012 only 15.01 lies on the cent grid, so even a large order resolves one share.
        self.assertEqual(resolve(5999, "89985.00", 6000, "15.000002", CENT), (D("15.01"), D("90000.01")))

    def test_several_execution_prices_in_one_report_need_reconciliation(self):
        # 99 x 0.9354 + 1 x 0.9355 in one snapshot: the notional 93.5401 is unique, but no single
        # on-grid price carries it, so one native fill cannot represent the shares.
        with self.assertRaisesRegex(ValueError, "cumulative_fill_precision_requires_reconciliation"):
            resolve(0, "0", 100, "0.935401", FOUR)

    def test_an_ambiguous_notional_is_refused_even_when_the_derived_price_is_on_grid(self):
        # After 299 x 0.9354, one share at 0.9356 reports 0.935401: the derived 0.9357 is on the grid
        # but five tick values fit within 300 x 0.000001, so it cannot be told from the truth.
        with self.assertRaisesRegex(ValueError, "cumulative_fill_precision_requires_reconciliation"):
            resolve(299, "279.6846", 300, "0.935401", FOUR)
        # 149 x 2.77 then 1 x 2.7701 reports 2.770001: 2.7701 and 2.7702 both fit within 150 x 0.000001.
        with self.assertRaisesRegex(ValueError, "cumulative_fill_precision_requires_reconciliation"):
            resolve(149, "412.73", 150, "2.770001", FOUR)

    def test_impossible_reports_are_refused(self):
        for args in ((1, "15.00", 2, "7", CENT), (2, "30", 2, "15", CENT), (1, "15", 2, "15.004", CENT)):
            with self.subTest(args=args):
                with self.assertRaisesRegex(ValueError, "cumulative_fill_precision_requires_reconciliation"):
                    resolve(*args)

    def test_a_sub_dollar_split_resolves_on_the_four_decimal_grid(self):
        # 2 x 0.9354 then 1 x 0.9355, reported 0.935433: 0.9355 is the only fit.
        self.assertEqual(resolve(2, "1.8708", 3, "0.935433", FOUR), (D("0.9355"), D("2.8063")))

    def test_the_callers_decimal_context_does_not_change_the_result(self):
        with localcontext() as ctx:
            ctx.prec = 6
            self.assertEqual(resolve(11, "165", 12, "15.000833", FOUR), (D("15.0100"), D("180.0100")))
            self.assertEqual(resolve(11, "165", 12, "15.000008", FOUR)[0], D("15.0001"))


class IncrementalBoundTests(unittest.TestCase):
    def test_bound_adds_both_reports_and_ignores_empty_ones(self):
        self.assertEqual(f.incremental_notional_bound(D(3), D("100.006667"), D(1), D("100")), D("0.000004"))
        self.assertEqual(f.incremental_notional_bound(D(3), D("100.01"), D(0), None), D("0.000003"))
        self.assertEqual(f.incremental_notional_bound(D(0), None, D(0), None), D(0))


if __name__ == "__main__":
    unittest.main()
