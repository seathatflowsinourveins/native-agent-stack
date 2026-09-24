"""cost_model: the v1 table by sha256, monotone tiers, half-open lookup, square-root impact, the half-spread floor,
fees with the TAF cap and amendments, the net-return formula and the cash band."""
import json
import tempfile
import unittest
from pathlib import Path

from core import costs
from core.params import COST_TABLE
from tests import synth

REPO = Path(__file__).resolve().parents[5]
PROTOCOL = json.loads((Path(__file__).resolve().parents[2] / "protocol-core-draft.json").read_text())

FEES = {"sec_section31_usd_per_million_of_sales": [
            {"from": "2016-10-01", "to": "2017-10-19", "rate": 21.80, "source": "synthetic"},
            {"from": "2017-10-20", "to": "2021-06-30", "rate": 13.00, "source": "synthetic"}],
        "finra_taf_covered_equity_sales": [
            {"from": "2016-01-01", "to": "2021-06-30", "usd_per_share": 0.000119, "max_per_trade": 5.95,
             "source": "synthetic"}]}


class Table(unittest.TestCase):
    def setUp(self):
        self.cells = costs.load_table(REPO / COST_TABLE["path"])

    def test_refuses_another_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "t.json"
            body = json.loads((REPO / COST_TABLE["path"]).read_text())
            body["cells"]["0|0|0"]["half_spread"] += 1e-9
            p.write_text(json.dumps(body))
            with self.assertRaises(costs.TableHashMismatch):
                costs.load_table(p)

    def test_monotone_fix_reproduces_the_protocol_cells_and_is_monotone(self):
        fixed = costs.monotone(self.cells)
        changed = {k: [round(self.cells[k] * 1e4, 2), round(fixed[k] * 1e4, 2)]
                   for k in self.cells if fixed[k] != self.cells[k]}
        self.assertEqual(changed, PROTOCOL["cost_model"]["fix_1_monotone_dollar_volume"]["cells_changed_bps_before_after"])
        for tb in range(4):
            for pt in range(4):
                self.assertGreaterEqual(fixed[f"{tb}|{pt}|0"], fixed[f"{tb}|{pt}|1"])
                self.assertGreaterEqual(fixed[f"{tb}|{pt}|1"], fixed[f"{tb}|{pt}|2"])

    def test_half_open_lookup(self):
        d = "2020-03-10"
        cal = synth.calendar()
        self.assertEqual(costs.cell_key(d, cal.at(d, "09:30"), 5.00, 1_000_000.0), "2|2|1")
        self.assertEqual(costs.cell_key(d, cal.at(d, "10:00"), 4.99, 999_999.0), "3|1|0")
        self.assertEqual(costs.cell_key(d, cal.at(d, "09:59") + 59.9, 20.0, 5_000_000.0), "2|3|2")
        self.assertEqual(costs.cell_key(d, cal.at(d, "15:55"), 1.99, 0.0), "3|0|0")
        with self.assertRaises(ValueError):
            costs.cell_key(d, cal.at(d, "16:02"), 5.0, 0.0)


class Sizing(unittest.TestCase):
    def test_notional_caps_and_no_fill(self):
        self.assertEqual(costs.filled_notional(10_000_000, 1_000_000), 20_000)
        self.assertEqual(costs.filled_notional(1_000_000, 1_000_000), 10_000)
        self.assertEqual(costs.filled_notional(10_000_000, 50_000), 5_000)
        self.assertTrue(costs.is_no_fill(costs.filled_notional(50_000, 1_000_000)))   # $500
        self.assertTrue(costs.is_no_fill(costs.filled_notional(None, 1_000_000)))
        self.assertTrue(costs.is_no_fill(costs.filled_notional(1_000_000, None)))
        self.assertFalse(costs.is_no_fill(1000.0))

    def test_square_root_impact(self):
        a = costs.impact(1.0, 0.05, 10_000, 1_000_000)
        b = costs.impact(1.0, 0.05, 40_000, 1_000_000)
        self.assertAlmostEqual(a, 0.05 * 0.1)
        self.assertAlmostEqual(b / a, 2.0)
        self.assertAlmostEqual(costs.impact(2.0, 0.05, 10_000, 1_000_000), 2 * a)

    def test_per_side_uses_the_realized_half_spread_floor(self):
        self.assertAlmostEqual(costs.per_side(0.002, 0.005, 0.001), 1.25 * 0.005 + 0.001)
        self.assertAlmostEqual(costs.per_side(0.006, 0.005, 0.001), 1.25 * 0.006 + 0.001)
        self.assertAlmostEqual(costs.per_side(0.002, 0.005, 0.001, "table_only"), 1.25 * 0.002 + 0.001)
        self.assertAlmostEqual(costs.per_side(0.002, 0.005, 0.002, "stress"), 2 * 1.25 * 0.005 + 0.002)


class Fees(unittest.TestCase):
    def test_2017_and_2019_sales_with_the_taf_cap(self):
        f = costs.Fees(FEES)
        self.assertAlmostEqual(f.sale_fees("2017-03-01", 1000, 10_000), 21.80 * 0.01 + 0.119)
        self.assertAlmostEqual(f.sale_fees("2019-06-03", 1000, 10_000), 13.00 * 0.01 + 0.119)
        self.assertAlmostEqual(f.sale_fees("2019-06-03", 100_000, 20_000), 13.00 * 0.02 + 5.95)  # capped

    def test_post_freeze_amendment_and_missing_cap(self):
        base = json.loads(json.dumps(FEES))
        base["sec_section31_usd_per_million_of_sales"][-1]["to"] = "2026-12-31"
        base["finra_taf_covered_equity_sales"][-1]["to"] = "2026-12-31"
        amended = costs.Fees(base, [
            {"kind": "finra_taf", "from": "2027-01-01", "to": "2027-12-31", "usd_per_share": 0.0002, "max_per_trade": 10.0},
            {"kind": "sec_section31", "from": "2027-01-01", "to": "2027-12-31", "rate": 30.0}])
        self.assertAlmostEqual(amended.sale_fees("2027-02-01", 1000, 10_000), 0.30 + 0.2)
        with self.assertRaises(ValueError):
            costs.Fees(base, [{"kind": "finra_taf", "from": "2027-01-01", "to": "2027-12-31", "usd_per_share": 0.0002}])
        # review round 9, F5: a line that starts before the freeze session is refused
        early = {"kind": "sec_section31", "from": "2020-01-01", "to": "2020-12-31", "rate": 99.0}
        with self.assertRaises(ValueError):
            costs.Fees(base, [early], freeze_session="2026-10-05")
        with tempfile.TemporaryDirectory() as tmp:
            b, a = Path(tmp) / "fees.json", Path(tmp) / "amend.jsonl"
            b.write_text(json.dumps(base))
            a.write_text(json.dumps(early) + "\n")
            with self.assertRaises(ValueError):          # no freeze session: the line cannot apply
                costs.Fees.from_files(b, a)
            with self.assertRaises(ValueError):
                costs.Fees.from_files(b, a, freeze_session="2026-10-05")
        with self.assertRaises(KeyError):
            costs.Fees(FEES).sale_fees("2021-07-06", 1, 1)


class NetReturn(unittest.TestCase):
    def test_formula_on_a_small_table(self):
        f = costs.Fees(FEES)
        # N = 10000 / 10 = 1000 shares; exit mid 11; c_in 0.01; c_out 0.02; F 1; cash 0
        net = costs.trade_net_return(10_000, 10.0, 11.0, 1.0, 0.0, 0.01, 0.02, f, "2019-06-03")
        fees = 13.0 * 11_000 / 1e6 + min(0.000119 * 1000, 5.95)
        self.assertAlmostEqual(net, (11_000 * 0.98 - fees) / (10_000 * 1.01) - 1)
        # a 2:1 split inside the hold: exit shares N x F, fees on N x F at the raw mid
        net2 = costs.trade_net_return(10_000, 10.0, 5.5, 2.0, 0.0, 0.01, 0.02, f, "2019-06-03")
        fees2 = 13.0 * 11_000 / 1e6 + min(0.000119 * 2000, 5.95)
        self.assertAlmostEqual(net2, (11_000 * 0.98 - fees2) / (10_000 * 1.01) - 1)
        # cash per original share
        net3 = costs.trade_net_return(10_000, 10.0, 11.0, 1.0, 0.5, 0.0, 0.0, f, "2019-06-03")
        self.assertAlmostEqual(net3, (11_000 - fees + 500) / 10_000 - 1)

    def test_cash_term_crossings(self):
        cal = synth.calendar()
        s = cal.range("2020-06-01", "2020-06-12")
        e, x = s[1], s[5]
        # an ordinary 1% dividend on s[3]: cash booked, F = 1
        raw, split, allc = synth.series(cal, s[0], s[-1], lambda d: 20.0 if d < s[3] else 19.8, cash_at={s[3]: 0.2})
        cash = costs.cash_term(raw[e]["c"], allc[e]["c"], raw[x]["c"], allc[x]["c"], 1.0)
        self.assertAlmostEqual(cash, 0.2, places=9)
        # a special 5% dividend: cash, never a share change (split-adjusted closes carry no dividend)
        raw, split, allc = synth.series(cal, s[0], s[-1], lambda d: 20.0 if d < s[3] else 19.0, cash_at={s[3]: 1.0})
        from core import formulas as FM
        self.assertEqual(FM.share_factor(raw, split, e, x), 1.0)
        self.assertFalse(FM.suspected_at(cal, raw, split, s[3]))
        self.assertAlmostEqual(costs.cash_term(raw[e]["c"], allc[e]["c"], raw[x]["c"], allc[x]["c"], 1.0), 1.0, places=9)
        # a 2:1 split: F = 2, cash 0
        raw, split, allc = synth.series(cal, s[0], s[-1], lambda d: 20.0 if d < s[3] else 10.0, split_at={s[3]: 2.0})
        F = FM.share_factor(raw, split, e, x)
        self.assertEqual(F, 2.0)
        self.assertEqual(costs.cash_term(raw[e]["c"], allc[e]["c"], raw[x]["c"], allc[x]["c"], F), 0.0)

    def test_cash_band_is_symmetric(self):
        # 5e-4 adjustment noise of either sign books 0 (review round 8, E6)
        self.assertEqual(costs.cash_term(10.0, 10.0, 10.0, 10.0 * (1 + 5e-4), 1.0), 0.0)
        self.assertEqual(costs.cash_term(10.0, 10.0, 10.0, 10.0 * (1 - 5e-4), 1.0), 0.0)
        self.assertAlmostEqual(costs.cash_term(10.0, 10.0, 10.0, 10.0 * (1 - 5e-3), 1.0), -0.05)


if __name__ == "__main__":
    unittest.main()
