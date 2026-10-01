"""Pure-module tests for the modeled margin-interest / financing lane
(financing.py). Stdlib only -- these run on plain system Python (no
jsonschema/PyYAML/numpy, no pinned runtime). See test_adaptive_paper_runner.py
for the runner.py integration test (overnight_holds False adds no outcome
key).

Fixture dates are verified directly against sessions.py's own
next_trading_day (see the module docstring's cited dates): 2026-09-15
(Tuesday) and 2026-09-16 are ordinary trading days with no 2026 holiday
nearby; 2026-09-10 (Thursday) settles Friday 2026-09-11 with an ordinary,
holiday-free weekend behind it; 2026-09-03 (Thursday) settles Friday
2026-09-04, whose weekend is immediately followed by the Labor Day holiday
(2026-09-07, in sessions.HOLIDAYS_2026), so the next trading day is Tuesday
2026-09-08.
"""
from datetime import date
from decimal import Decimal as D
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))  # financing.py imports the sibling sessions module
SPEC = importlib.util.spec_from_file_location("adaptive_paper_financing", SOURCE / "financing.py")
F = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = F
SPEC.loader.exec_module(F)


class WorkedExampleTests(unittest.TestCase):
    """Alpaca "Margin and Short Selling": deposit $10,000, buy $15,000, hold
    at end of day -> borrows $5,000 overnight."""

    TRADE_DATE = date(2026, 9, 15)  # ordinary Tuesday, no 2026 holiday nearby

    def test_standard_rate_is_zero_point_nine_zero_per_day(self):
        result = F.overnight_financing_projection(D("15000"), D("10000"), self.TRADE_DATE, "standard")
        self.assertEqual(result["debit_usd"], D("5000"))
        self.assertEqual(result["charge_days"], 1)
        self.assertEqual(result["rate"], D("0.0650"))
        # Exact, unrounded: 5000 * 0.065 / 360 -- the doc's own worked-example arithmetic.
        self.assertEqual(result["daily_charge_usd"], D("5000") * D("0.0650") / 360)
        self.assertEqual(F.quantize_cents(result["total_charge_usd"]), D("0.90"))
        self.assertEqual(result["source"], F.RATE_SOURCE)

    def test_elite_rate_is_zero_point_six_nine_repeating_per_day(self):
        result = F.overnight_financing_projection(D("15000"), D("10000"), self.TRADE_DATE, "elite")
        self.assertEqual(result["rate"], D("0.0500"))
        self.assertEqual(result["daily_charge_usd"], D("5000") * D("0.0500") / 360)
        self.assertEqual(F.quantize_cents(result["total_charge_usd"]), D("0.69"))
        # Full (unrounded) precision is kept by default: 0.69444... repeats past 2dp.
        self.assertNotEqual(result["total_charge_usd"], F.quantize_cents(result["total_charge_usd"]))


class FridayThreeDayAccrualTests(unittest.TestCase):
    """"A settlement-date debit balance at the end of day Friday incurs 3
    days of interest (Fri, Sat, Sun)" -- an ordinary, holiday-free week."""

    BUY_DATE = date(2026, 9, 10)  # Thursday; settles Friday 2026-09-11

    def test_friday_balance_accrues_for_friday_saturday_sunday(self):
        schedule = F.settled_debit_schedule(D("10000"), [(self.BUY_DATE, D("-15000"))],
                                            date(2026, 9, 10), date(2026, 9, 13))  # Thu..Sun
        by_date = {row["date"]: row for row in schedule}
        self.assertEqual(by_date[date(2026, 9, 10)]["debit_usd"], D("0"))  # trade-date night: not yet settled
        for d in (date(2026, 9, 11), date(2026, 9, 12), date(2026, 9, 13)):
            self.assertEqual(by_date[d]["debit_usd"], D("5000"), d)
            self.assertEqual(by_date[d]["balance_usd"], D("-5000"), d)
        result = F.margin_interest(schedule, "standard")
        self.assertEqual(len(result["daily"]), 4)
        expected_daily = D("5000") * D("0.0650") / 360
        # Mirror margin_interest's own left-to-right accumulation (starting
        # at 0, one Decimal addition per day) rather than a single
        # multiplication: the two can differ in the last of 28 significant
        # digits, since each addition re-rounds to context precision.
        expected_total = D("0") + D("0") + expected_daily + expected_daily + expected_daily
        self.assertEqual(result["total_usd"], expected_total)
        self.assertEqual(F.quantize_cents(result["total_usd"]), F.quantize_cents(expected_daily * 3))


class SettlementOffsetTests(unittest.TestCase):
    """A flow is counted from its settlement date, never its trade date."""

    def test_buy_settles_t_plus_1_no_charge_trade_date_night(self):
        trade_date = date(2026, 9, 15)
        schedule = F.settled_debit_schedule(D("10000"), [(trade_date, D("-15000"))], trade_date, trade_date)
        self.assertEqual(len(schedule), 1)
        self.assertEqual(schedule[0]["debit_usd"], D("0"))
        self.assertEqual(schedule[0]["balance_usd"], D("10000"))

    def test_debit_appears_on_the_settlement_date(self):
        trade_date = date(2026, 9, 15)
        settle = F.settlement_date(trade_date)
        self.assertEqual(settle, date(2026, 9, 16))
        schedule = F.settled_debit_schedule(D("10000"), [(trade_date, D("-15000"))], trade_date, settle)
        by_date = {row["date"]: row for row in schedule}
        self.assertEqual(by_date[trade_date]["debit_usd"], D("0"))
        self.assertEqual(by_date[settle]["debit_usd"], D("5000"))


class WeekendAndHolidaySettleWindowTests(unittest.TestCase):
    """A one-night hold whose buy settlement lands the Friday before Labor
    Day (2026-09-07, sessions.HOLIDAYS_2026): the settle-to-settle window
    spans Friday, Saturday, Sunday and the Monday holiday."""

    def test_charge_days_span_weekend_and_labor_day_holiday(self):
        trade_date = date(2026, 9, 3)  # Thursday
        result = F.overnight_financing_projection(D("15000"), D("10000"), trade_date, "standard")
        self.assertEqual(result["trade_date"], trade_date)
        self.assertEqual(result["buy_settlement_date"], date(2026, 9, 4))  # Friday
        self.assertEqual(result["next_session_date"], date(2026, 9, 4))  # the next trading session
        self.assertEqual(result["sell_settlement_date"], date(2026, 9, 8))  # Tue (Mon 9/7 = Labor Day)
        self.assertEqual(result["charge_days"], 4)
        expected_daily = D("5000") * D("0.0650") / 360
        self.assertEqual(result["total_charge_usd"], expected_daily * 4)


class NoDebitTests(unittest.TestCase):
    def test_no_debit_when_settled_cash_covers_the_book(self):
        result = F.overnight_financing_projection(D("5000"), D("10000"), date(2026, 9, 15), "standard")
        self.assertEqual(result["debit_usd"], D("0"))
        self.assertEqual(result["daily_charge_usd"], D("0"))
        self.assertEqual(result["total_charge_usd"], D("0"))

    def test_settled_debit_schedule_reports_zero_debit_when_cash_covers_flows(self):
        schedule = F.settled_debit_schedule(D("20000"), [(date(2026, 9, 15), D("-15000"))],
                                            date(2026, 9, 15), date(2026, 9, 17))
        self.assertTrue(all(row["debit_usd"] == D("0") for row in schedule))


class UnknownPlanTests(unittest.TestCase):
    def test_overnight_financing_projection_refuses_unknown_plan(self):
        with self.assertRaises(ValueError):
            F.overnight_financing_projection(D("15000"), D("10000"), date(2026, 9, 15), "gold")

    def test_margin_interest_refuses_unknown_plan(self):
        schedule = F.settled_debit_schedule(D("10000"), [(date(2026, 9, 15), D("-15000"))],
                                            date(2026, 9, 15), date(2026, 9, 16))
        with self.assertRaises(ValueError):
            F.margin_interest(schedule, "gold")


class DecimalPrecisionTests(unittest.TestCase):
    def test_margin_interest_keeps_full_precision_until_quantized(self):
        schedule = F.settled_debit_schedule(D("10000"), [(date(2026, 9, 15), D("-15000"))],
                                            date(2026, 9, 16), date(2026, 9, 16))
        result = F.margin_interest(schedule, "elite")
        # 5000 * 0.05 / 360 has a non-terminating decimal expansion; unrounded
        # it must carry more than 2 fractional digits (i.e. not pre-quantized).
        exponent = result["total_usd"].as_tuple().exponent
        self.assertLess(exponent, -2)
        self.assertEqual(result["total_usd"], D("5000") * D("0.0500") / 360)

    def test_quantize_cents_only_rounds_when_explicitly_called(self):
        value = D("0.9027777777777777777777777778")
        self.assertNotEqual(value, D("0.90"))
        self.assertEqual(F.quantize_cents(value), D("0.90"))


if __name__ == "__main__":
    unittest.main()
