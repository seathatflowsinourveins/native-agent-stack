"""Local negative tests of replay admission/oracle; no broker or engine substitute."""
import copy
from datetime import date, datetime, time
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "blueprints/us-equities/engine-nautilus/equity-replay"
SPEC = importlib.util.spec_from_file_location("equity_replay", SOURCE / "run.py")
REPLAY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPLAY)


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads((SOURCE / "plan.json").read_text())
        self.rows = [{"symbol": "AAPL", "session_date": date.fromordinal(i).isoformat(),
                      "o": "100", "h": "102", "l": "99", "c": "101", "v": "1000000"}
                     for i in range(date(2020, 8, 10).toordinal(), date(2020, 8, 28).toordinal() + 1)
                     if date.fromordinal(i).weekday() < 5]
        self.stages = {"bars": {"status": "complete", "rows": self.rows},
                       "actions": {"status": "complete", "rows": [{"ex_date": "2020-08-07"}, {"ex_date": "2020-08-31"}]}}

    def test_clean_interval_and_neighbor_actions(self):
        self.assertEqual(REPLAY.select_rows(self.stages, self.plan), self.rows)

    def test_missing_duplicate_and_reordered_sessions(self):
        for rows in (self.rows[:-1], self.rows[:-1] + [self.rows[0]], list(reversed(self.rows))):
            with self.subTest(rows=rows[-1]["session_date"]), self.assertRaisesRegex(ValueError, "session_coverage"):
                REPLAY.select_rows({**self.stages, "bars": {"status": "complete", "rows": rows}}, self.plan)

    def test_incomplete_source_and_overlapping_actions(self):
        for actions in ({"status": "failed", "rows": []}, {"status": "complete", "rows": [{"ex_date": "2020-08-10"}]},
                        {"status": "complete", "rows": [{}]}):
            with self.subTest(actions=actions), self.assertRaises(ValueError):
                REPLAY.select_rows({**self.stages, "actions": actions}, self.plan)

    def test_numeric_and_participation_refusals(self):
        for change in ({"c": "NaN"}, {"c": "103"}, {"v": "0"}, {"v": "1.5"}, {"v": "100"},
                       {"c": "100.12345"}, {"symbol": "META"}):
            stages = copy.deepcopy(self.stages)
            stages["bars"]["rows"][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                REPLAY.select_rows(stages, self.plan)

    def reports(self):
        case = self.plan["cases"][0]
        fills, positions = [], []
        cash = Decimal(self.plan["capital_usd"])
        accounts = [{"currency": "USD", "total": str(cash)}]
        schedule = sorted([(i, "BUY") for i in self.plan["entry_indices"]] + [(i, "SELL") for i in self.plan["exit_indices"]])
        for n, (index, side) in enumerate(schedule):
            stamp = int(datetime.combine(date.fromisoformat(self.rows[index]["session_date"]), time(16), ZoneInfo("America/New_York")).timestamp()) * 1000
            fills.append({"venue_order_id": str(n), "instrument_id": "AAPL.SIM", "status": "FILLED", "side": side,
                          "quantity": "10", "filled_qty": "10", "avg_px": "101", "ts_init": stamp,
                          "ts_last": stamp, "commissions": ["0.00 USD"]})
            cash += Decimal(-1010 if side == "BUY" else 1010)
            accounts.append({"currency": "USD", "total": str(cash)})
            if side == "SELL":
                positions.append({"side": "FLAT", "quantity": "0", "ts_closed": stamp, "realized_pnl": "0.00 USD"})
        return case, fills, positions, accounts

    def test_synthetic_oracle_control(self):
        case, fills, positions, accounts = self.reports()
        result = REPLAY.audit_reports(self.rows, self.plan, case, fills, positions, accounts)
        self.assertEqual(result["cash_transitions_verified"], 10)

    def test_oracle_rejects_price_schedule_fee_currency_and_identity_changes(self):
        for key, value in (("avg_px", "101.01"), ("ts_last", 0), ("side", "SELL"), ("status", "PARTIALLY_FILLED"),
                           ("filled_qty", "9"), ("commissions", ["1.00 USD"]), ("commissions", ["0.00 EUR"]), ("venue_order_id", "1")):
            case, fills, positions, accounts = self.reports()
            fills[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                REPLAY.audit_reports(self.rows, self.plan, case, fills, positions, accounts)

    def test_oracle_rejects_intermediate_cash_even_when_final_matches(self):
        case, fills, positions, accounts = self.reports()
        accounts[3]["total"] = "99999"
        with self.assertRaisesRegex(ValueError, "cash_transition"):
            REPLAY.audit_reports(self.rows, self.plan, case, fills, positions, accounts)

    def test_oracle_requires_flat_position_and_realized_pnl(self):
        for update in ({"quantity": "1"}, {"ts_closed": None}, {"realized_pnl": "1.00 USD"}):
            case, fills, positions, accounts = self.reports()
            positions[0].update(update)
            with self.subTest(update=update), self.assertRaises(ValueError):
                REPLAY.audit_reports(self.rows, self.plan, case, fills, positions, accounts)


if __name__ == "__main__":
    unittest.main()
