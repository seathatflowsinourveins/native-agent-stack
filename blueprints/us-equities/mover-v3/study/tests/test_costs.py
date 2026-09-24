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


class FeeSupersession(unittest.TestCase):
    """Review round 14, F2: an SEC or TAF rate change after the freeze is representable over an open-ended base row,
    base rows that overlap are refused at load, and a count or read refuses a fee gap before it fetches or logs."""

    def test_an_amendment_supersedes_an_open_ended_base_row(self):
        base = json.loads(json.dumps(FEES))
        base["sec_section31_usd_per_million_of_sales"][-1]["to"] = "2099-12-31"      # open-ended, as pinned
        base["finra_taf_covered_equity_sales"][-1]["to"] = "2099-12-31"
        f = costs.Fees(base, [{"kind": "sec_section31", "from": "2027-05-14", "to": "2099-12-31", "rate": 27.8},
                              {"kind": "sec_section31", "from": "2027-10-01", "to": "2099-12-31", "rate": 20.6}],
                       freeze_session="2026-10-05")
        self.assertEqual(f.rates("2027-05-13")[0], 13.00)
        self.assertEqual(f.rates("2027-05-14")[0], 27.8)
        self.assertEqual(f.rates("2027-10-01")[0], 20.6)          # the latest appended line that covers the date
        self.assertEqual(f.gaps(["2027-05-14", "2027-10-01"]), [])

    def test_overlapping_base_rows_are_refused_and_gaps_are_named(self):
        bad = json.loads(json.dumps(FEES))
        bad["sec_section31_usd_per_million_of_sales"][0]["to"] = "2017-10-20"
        with self.assertRaisesRegex(ValueError, "overlap"):
            costs.Fees(bad)
        f = costs.Fees(FEES)                                      # the base ends 2021-06-30
        self.assertEqual(f.gaps(["2021-06-30", "2021-07-01", "2021-07-02"]), ["2021-07-01", "2021-07-02"])

    def test_a_count_or_read_refuses_a_fee_gap_before_it_fetches(self):
        from core import holdout, logs
        cal = synth.calendar(last="2021-12-31")
        ctx = {"cal": cal, "fees": costs.Fees(FEES)}
        with self.assertRaisesRegex(holdout.HoldoutRefused, "no governing fee row .first 2021-07-01"):
            holdout.require_fee_coverage(ctx, ["2021-06-25", "2021-07-09"])
        holdout.require_fee_coverage(ctx, ["2021-06-01", "2021-06-30"])
        # a '_fetch' line's dates are a first use: no fee line for them can be added between seal and evaluation
        line = {"stage": "holdout", "purpose": "read_fetch", "utc_start": "2021-07-12T21:00:00Z",
                "sessions": ["2021-06-01", "2021-06-30"], "fee_span": ["2021-06-01", "2021-07-08"]}
        use = logs.fee_first_use([{"kind": "sec_section31", "from": "2021-07-01", "to": "2021-12-31"}], [line])
        self.assertIn(0, use)


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
        self.assertAlmostEqual(costs.cash_term(raw, split, allc, e, x), 0.2, places=9)
        # a special 5% dividend: cash, never a share change (split-adjusted closes carry no dividend)
        raw, split, allc = synth.series(cal, s[0], s[-1], lambda d: 20.0 if d < s[3] else 19.0, cash_at={s[3]: 1.0})
        from core import formulas as FM
        self.assertEqual(FM.share_factor(raw, split, e, x), 1.0)
        self.assertFalse(FM.suspected_at(cal, raw, split, s[3]))
        self.assertAlmostEqual(costs.cash_term(raw, split, allc, e, x), 1.0, places=9)
        # a 2:1 split: F = 2, cash 0
        raw, split, allc = synth.series(cal, s[0], s[-1], lambda d: 20.0 if d < s[3] else 10.0, split_at={s[3]: 2.0})
        self.assertEqual(FM.share_factor(raw, split, e, x), 2.0)
        self.assertEqual(costs.cash_term(raw, split, allc, e, x), 0.0)
        # a 2:1 split before a $0.20 dividend per new share: 2 new shares per original share receive 0.40
        raw, split, allc = synth.series(cal, s[0], s[-1], lambda d: 20.0 if d < s[2] else (10.0 if d < s[3] else 9.8),
                                        split_at={s[2]: 2.0}, cash_at={s[3]: 0.2})
        self.assertAlmostEqual(costs.cash_term(raw, split, allc, e, x), 0.4, places=9)
        # a missing bar inside the hold is skipped; a missing bar at e or x leaves the cash undefined
        raw, split, allc = synth.series(cal, s[0], s[-1], lambda d: 20.0 if d < s[3] else 19.8, cash_at={s[3]: 0.2},
                                        missing=(s[2],))
        self.assertAlmostEqual(costs.cash_term(raw, split, allc, e, x), 0.2, places=9)
        self.assertIsNone(costs.cash_term(raw, split, allc, s[2], x))

    def test_cash_does_not_move_with_prices_after_the_ex_date(self):
        """Review round 14, Codex P2: entry close $20, a $1 dividend ex on x, an overnight exit at x's open. D7's
        formula booked cash 1 with x's close at 19 and cash 2 with x's close at 38; the cash is 1 either way."""
        cal = synth.calendar()
        s = cal.range("2020-06-01", "2020-06-05")
        e, x = s[1], s[2]
        for close_x in (19.0, 38.0):
            raw, split, allc = synth.series(cal, s[0], s[-1], lambda d: 20.0 if d < x else close_x,
                                            cash_at={x: 1.0})
            self.assertAlmostEqual(costs.cash_term(raw, split, allc, e, x), 1.0, places=9)

    def test_cash_band_is_symmetric(self):
        # 5e-4 adjustment noise of either sign books 0 (review round 8, E6); a 5e-3 step books with its sign
        cal = synth.calendar()
        s = cal.range("2020-06-01", "2020-06-05")
        bar = lambda c: {"o": c, "h": c, "l": c, "c": c, "v": 1}  # noqa: E731
        raw = {d: bar(10.0) for d in s}
        for eps, want in ((5e-4, 0.0), (-5e-4, 0.0), (-5e-3, 10.0 * (1 - 1 / (1 - 5e-3)))):
            allc = {d: bar(10.0 * (1 + eps) if d == s[3] else 10.0) for d in s}
            self.assertAlmostEqual(costs.cash_term(raw, raw, allc, s[1], s[3]), want, places=12)


if __name__ == "__main__":
    unittest.main()
