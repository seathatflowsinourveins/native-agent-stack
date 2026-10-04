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

FEES = synth.fee_document([("2016-10-01", "2017-10-19", 21.80), ("2017-10-20", "2021-06-30", 13.00)],
                          [("2016-01-01", "2021-06-30", 0.000119, 5.95)])


def fee_cal():
    """The calendar the fee tests settle on (review round 15, fee-date item)."""
    return synth.calendar("2015-09-01", "2028-12-29")


def fee_table(doc=FEES, lines=(), **kw):
    return costs.Fees(doc, lines, cal=fee_cal(), **kw)


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
        f = fee_table()
        self.assertAlmostEqual(f.sale_fees("2017-03-01", 1000, 10_000), 21.80 * 0.01 + 0.119)
        self.assertAlmostEqual(f.sale_fees("2019-06-03", 1000, 10_000), 13.00 * 0.01 + 0.119)
        self.assertAlmostEqual(f.sale_fees("2019-06-03", 100_000, 20_000), 13.00 * 0.02 + 5.95)  # capped

    def test_post_freeze_amendment_and_missing_cap(self):
        base = json.loads(json.dumps(FEES))
        base["sec_section31"]["rows"][-1]["to"] = "2026-12-31"
        base["finra_taf_covered_equity"]["rows"][-1]["to"] = "2026-12-31"
        amended = fee_table(base, [
            synth.fee_line("finra_taf_covered_equity", "2027-01-01", "2027-12-31", usd_per_share=0.0002,
                           max_usd_per_trade=10.0),
            synth.fee_line("sec_section31", "2027-01-01", "2027-12-31", usd_per_million=30.0)])
        self.assertAlmostEqual(amended.sale_fees("2027-02-01", 1000, 10_000), 0.30 + 0.2)
        with self.assertRaises(ValueError):
            fee_table(base, [synth.fee_line("finra_taf_covered_equity", "2027-01-01", "2027-12-31",
                                       usd_per_share=0.0002)])
        # review round 9, F5: a line that starts before the freeze session is refused
        early = synth.fee_line("sec_section31", "2020-01-01", "2020-12-31", usd_per_million=99.0)
        with self.assertRaises(ValueError):
            fee_table(base, [early], freeze_session="2026-10-05")
        with tempfile.TemporaryDirectory() as tmp:
            b, a = Path(tmp) / "fees.json", Path(tmp) / "amend.jsonl"
            b.write_text(json.dumps(base))
            a.write_text(json.dumps(early) + "\n")
            with self.assertRaises(ValueError):          # no freeze session: the line cannot apply
                costs.Fees.from_files(b, a, cal=fee_cal())
            with self.assertRaises(ValueError):
                costs.Fees.from_files(b, a, freeze_session="2026-10-05", cal=fee_cal())
        with self.assertRaises(KeyError):
            fee_table().sale_fees("2021-07-06", 1, 1)


class FeeSupersession(unittest.TestCase):
    """Review round 14, F2: an SEC or TAF rate change after the freeze is representable over an open-ended base row,
    base rows that overlap are refused at load, and a count or read refuses a fee gap before it fetches or logs."""

    def test_an_amendment_supersedes_an_open_ended_base_row(self):
        base = json.loads(json.dumps(FEES))
        base["sec_section31"]["rows"][-1]["to"] = None               # open-ended, as pinned
        base["finra_taf_covered_equity"]["rows"][-1]["to"] = None
        f = fee_table(base, [synth.fee_line("sec_section31", "2027-05-14", None, usd_per_million=27.8),
                        synth.fee_line("sec_section31", "2027-10-01", None, usd_per_million=20.6)],
                 freeze_session="2026-10-05")
        # T+1 in 2027: a sale on 2027-05-12 settles 2027-05-13, one on 2027-05-13 settles 2027-05-14 (a SEC row is
        # chosen by the charge date, cost_model.fee_charge_dates)
        self.assertEqual(f.rates("2027-05-12")[0], 13.00)
        self.assertEqual(f.rates("2027-05-13")[0], 27.8)
        self.assertEqual(f.rates("2027-10-01")[0], 20.6)          # the latest appended line that covers the date
        self.assertEqual(f.gaps(["2027-05-13", "2027-10-01"]), [])

    def test_overlapping_base_rows_are_refused_and_gaps_are_named(self):
        bad = json.loads(json.dumps(FEES))
        bad["sec_section31"]["rows"][0]["to"] = "2017-10-20"
        with self.assertRaisesRegex(ValueError, "overlap"):
            fee_table(bad)
        f = fee_table()                                                # the base ends 2021-06-30
        # T+2: a sale on 2021-06-28 settles 2021-06-30; one on 2021-06-29 settles 2021-07-01, after the SEC rows
        self.assertEqual(f.gaps(["2021-06-28", "2021-06-29", "2021-06-30", "2021-07-01"]),
                         ["2021-06-29", "2021-06-30", "2021-07-01"])

    def test_a_count_or_read_refuses_a_fee_gap_before_it_fetches(self):
        from core import holdout, logs
        cal = synth.calendar(last="2021-12-31")
        ctx = {"cal": cal, "fees": costs.Fees(FEES, cal=cal)}
        with self.assertRaisesRegex(holdout.HoldoutRefused, "no governing fee row .first 2021-06-29"):
            holdout.require_fee_coverage(ctx, ["2021-06-25", "2021-07-09"])
        holdout.require_fee_coverage(ctx, ["2021-06-01", "2021-06-28"])
        # a '_fetch' line's dates are a first use: no fee line for them can be added between seal and evaluation
        line = {"stage": "holdout", "purpose": "read_fetch", "utc_start": "2021-07-12T21:00:00Z",
                "sessions": ["2021-06-01", "2021-06-30"], "fee_span": ["2021-06-01", "2021-07-08"]}
        use = logs.fee_first_use([{"kind": "sec_section31", "from": "2021-07-01", "to": "2021-12-31"}], [line])
        self.assertIn(0, use)


class ChargeDates(unittest.TestCase):
    """Review round 15, fee-date item: the SEC Section 31 row is the one in force on the sale's charge date, its
    settlement date under the cycle in force on its trade date (T+3 before 2017-09-05, T+2 from then, T+1 from
    2024-05-28), counted in settlement days (sessions plus sourced exchange-only closures, excluding Columbus Day
    and Veterans Day); the FINRA TAF row is the one in force on the trade date. At e7529b47 both rows were chosen by
    the trade date."""

    def setUp(self):
        from core.calendar import Calendar
        data = Path(__file__).resolve().parents[2] / "data"
        self.cal = Calendar.from_files(data / "session-calendar.json")
        self.f = costs.Fees.from_files(data / "fees-v3.json", data / "fees-v3-amendments.jsonl", cal=self.cal)

    def test_settlement_cycles_and_their_transitions(self):
        sd = lambda d: costs.settlement_date(self.cal, d)    # noqa: E731
        self.assertEqual(sd("2017-06-28"), "2017-07-03")      # T+3
        self.assertEqual(sd("2017-06-29"), "2017-07-05")      # T+3 across Independence Day
        self.assertEqual(sd("2017-09-01"), "2017-09-07")      # the last T+3 trade, across Labor Day
        self.assertEqual(sd("2017-09-05"), "2017-09-07")      # the first T+2 trade (SEC statement 2017-163)
        self.assertEqual(sd("2024-05-24"), "2024-05-29")      # the last T+2 trade, across Memorial Day
        self.assertEqual(sd("2024-05-28"), "2024-05-29")      # the first T+1 trade (compliance date)
        self.assertEqual(sd("2018-11-09"), "2018-11-14")      # T+2 across Veterans Day observed on 2018-11-12
        self.assertEqual(sd("2027-10-08"), "2027-10-12")      # T+1 across Columbus Day 2027-10-11
        self.assertEqual(sd("2017-07-04"), None)              # not a session
        self.assertEqual(costs.bank_only_holidays(2018), frozenset({"2018-10-08", "2018-11-12"}))
        self.assertEqual(costs.bank_only_holidays(2017), frozenset({"2017-10-09"}))   # Nov 11 on a Saturday

    def test_settlement_on_2025_mourning_day_despite_exchange_closure(self):
        # Nasdaq ECA2024-632: January 8 trades settle January 9, which is not a trade date.
        # https://classic.nasdaqtrader.com/TraderNews.aspx?id=ECA2024-632
        self.assertFalse(self.cal.is_session("2025-01-09"))
        self.assertEqual(costs.settlement_date(self.cal, "2025-01-08"), "2025-01-09")
        self.assertIsNone(costs.settlement_date(self.cal, "2025-01-09"))
        self.assertEqual(costs.settlement_date(self.cal, "2025-01-10"), "2025-01-13")

    def test_settlement_on_2018_mourning_day_despite_exchange_closure(self):
        # Nasdaq ETA2018-99: December 3 trades settle December 5 under T+2.
        # https://www.nasdaqtrader.com/TraderNews.aspx?id=ETA2018-99
        self.assertFalse(self.cal.is_session("2018-12-05"))
        self.assertEqual(costs.settlement_date(self.cal, "2018-12-03"), "2018-12-05")
        self.assertEqual(costs.settlement_date(self.cal, "2018-12-04"), "2018-12-06")
        self.assertIsNone(costs.settlement_date(self.cal, "2018-12-05"))

    def test_sec_fee_boundary_after_2025_mourning_day(self):
        # Synthetic rates expose the wrong charge date; no historical rate changes on January 10.
        doc = synth.fee_document(
            [("2025-01-01", "2025-01-09", 10.0), ("2025-01-10", None, 20.0)],
            [("2025-01-01", "2025-01-08", 0.01, 10.0), ("2025-01-09", None, 0.02, 10.0)])
        fees = costs.Fees(doc, cal=self.cal)
        self.assertEqual(fees.sale_fees("2025-01-08", 100, 1_000_000), 11.0)
        self.assertEqual(fees.rates("2025-01-08"), (10.0, 0.01, 10.0))
        self.assertEqual(fees.sale_fees("2025-01-10", 100, 1_000_000), 22.0)

    def test_sec_rows_cross_on_the_settlement_date_and_taf_rows_on_the_trade_date(self):
        sec = lambda d: self.f.rates(d)[0]                   # noqa: E731
        self.assertEqual(sec("2017-06-28"), 21.80)            # settles 2017-07-03, before the 2017-07-04 row
        self.assertEqual(sec("2017-06-29"), 23.10)            # settles 2017-07-05 (by trade date: 21.80)
        self.assertEqual(sec("2020-02-12"), 20.70)            # settles 2020-02-14
        self.assertEqual(sec("2020-02-13"), 22.10)            # settles 2020-02-18, the row's first day
        self.assertEqual(sec("2024-05-17"), 8.00)             # settles 2024-05-21
        self.assertEqual(sec("2024-05-20"), 27.80)            # settles 2024-05-22 (by trade date: 8.00)
        self.assertEqual(sec("2021-02-22"), 22.10)            # settles 2021-02-24
        self.assertEqual(sec("2021-02-23"), 5.10)             # settles 2021-02-25, the row's first day
        taf = lambda d: self.f.rates(d)[1:]                  # noqa: E731
        self.assertEqual(taf("2021-12-31"), (0.000119, 5.95))  # by trade date, though it settles in 2022
        self.assertEqual(taf("2022-01-03"), (0.000130, 6.49))
        self.assertEqual(taf("2026-09-30"), (0.000195, 9.79))  # the last trade date before the TAF pause
        self.assertEqual(taf("2026-10-01"), (0.0, 0.0))

    def test_no_base_sec_boundary_depends_on_a_bank_only_holiday(self):
        """The settlement-day rule decides a row only where a SEC row starts within k settlement days after a bank
        holiday the exchange keeps open; no row of the committed file does, so the pinned rows' selection is the
        same with or without it (a later amendment line is dated by the same rule)."""
        doc = json.loads((Path(__file__).resolve().parents[2] / "data" / "fees-v3.json").read_text())
        for row in doc["sec_section31"]["rows"][1:]:
            start = row["from"]
            first = self.cal.next_on_or_after(start)
            window = self.cal.range(self.cal.offset(first, -4), first)
            hol = {h for d in window for h in costs.bank_only_holidays(int(d[:4]))}
            self.assertFalse(hol & set(window), start)


class PinnedDataFiles(unittest.TestCase):
    """Review round 15, N01: the loaders read the committed data files in their own schemas. The former loaders read
    a {"d", "open", "close"} dictionary per session and fee rows keyed sec_section31_usd_per_million_of_sales / rate
    and finra_taf_covered_equity_sales / max_per_trade, so neither committed file loaded (KeyError), and the synthetic
    fixtures used the loaders' format instead of the committed one."""

    DATA = Path(__file__).resolve().parents[2] / "data"

    def test_the_committed_fee_file_loads_and_covers_every_development_and_validation_sale(self):
        from core.calendar import Calendar
        cal = Calendar.from_files(self.DATA / "session-calendar.json")
        f = costs.Fees.from_files(self.DATA / "fees-v3.json", self.DATA / "fees-v3-amendments.jsonl", cal=cal)
        cases = {"2017-01-03": (21.80, 0.000119, 5.95), "2017-07-05": (23.10, 0.000119, 5.95),
                 "2019-06-03": (20.70, 0.000119, 5.95), "2020-12-31": (22.10, 0.000119, 5.95),
                 "2022-05-16": (22.90, 0.000130, 6.49), "2026-10-01": (20.60, 0.0, 0.0),
                 "2030-12-30": (20.60, 0.00024, 12.05)}                  # the open-ended SEC row
        for day, want in cases.items():
            self.assertEqual(f.rates(day), want, day)
        # a development sale is booked from the first development entry through E+5 of the last validation trade
        days = cal.range("2017-01-03", cal.offset("2020-12-31", 12))
        self.assertEqual(f.gaps(days), [])

    def test_the_pre_round_15_fee_format_is_refused(self):
        old = {"sec_section31_usd_per_million_of_sales": [{"from": "2016-01-01", "to": "2030-12-31", "rate": 8.0}],
               "finra_taf_covered_equity_sales": [{"from": "2016-01-01", "to": "2030-12-31", "usd_per_share": 0.0001,
                                                   "max_per_trade": 5.0}]}
        with self.assertRaises(costs.FeeSchemaError):
            fee_table(old)
        doc = json.loads((self.DATA / "fees-v3.json").read_text())
        doc["sec_section31"]["unit"] = "US dollars per thousand dollars"          # a unit change is refused
        with self.assertRaises(costs.FeeSchemaError):
            fee_table(doc)


class NetReturn(unittest.TestCase):
    def test_formula_on_a_small_table(self):
        f = fee_table()
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
        self.assertAlmostEqual(costs.cash_term(cal, raw, split, allc, e, x), 0.2, places=9)
        # a special 5% dividend: cash, never a share change (split-adjusted closes carry no dividend)
        raw, split, allc = synth.series(cal, s[0], s[-1], lambda d: 20.0 if d < s[3] else 19.0, cash_at={s[3]: 1.0})
        from core import formulas as FM
        self.assertEqual(FM.share_factor(raw, split, e, x), 1.0)
        self.assertFalse(FM.suspected_at(cal, raw, split, s[3]))
        self.assertAlmostEqual(costs.cash_term(cal, raw, split, allc, e, x), 1.0, places=9)
        # a 2:1 split: F = 2, cash 0
        raw, split, allc = synth.series(cal, s[0], s[-1], lambda d: 20.0 if d < s[3] else 10.0, split_at={s[3]: 2.0})
        self.assertEqual(FM.share_factor(raw, split, e, x), 2.0)
        self.assertEqual(costs.cash_term(cal, raw, split, allc, e, x), 0.0)
        # a 2:1 split before a $0.20 dividend per new share: 2 new shares per original share receive 0.40
        raw, split, allc = synth.series(cal, s[0], s[-1], lambda d: 20.0 if d < s[2] else (10.0 if d < s[3] else 9.8),
                                        split_at={s[2]: 2.0}, cash_at={s[3]: 0.2})
        self.assertAlmostEqual(costs.cash_term(cal, raw, split, allc, e, x), 0.4, places=9)
        # a missing bar inside the hold with no step across it books as before; a missing bar at e or x, or the
        # missing close before an ex-date, leaves the cash undefined (review of 202968f, Codex P2)
        raw, split, allc = synth.series(cal, s[0], s[-1], lambda d: 20.0 if d < s[3] else 19.8, cash_at={s[3]: 0.2},
                                        missing=(s[4],))
        self.assertAlmostEqual(costs.cash_term(cal, raw, split, allc, e, x), 0.2, places=9)
        self.assertIsNone(costs.cash_term(cal, raw, split, allc, s[4], x))
        raw, split, allc = synth.series(cal, s[0], s[-1], lambda d: 20.0 if d < s[3] else 19.8, cash_at={s[3]: 0.2},
                                        missing=(s[2],))
        self.assertIsNone(costs.cash_term(cal, raw, split, allc, e, x))

    def test_a_dividend_whose_previous_close_is_missing_is_never_priced_at_an_older_close(self):
        """Review of 202968f, Codex P2: closes $20, $40, $39, $39, $39 over e .. x and a $1 dividend ex on the third
        session. With every bar the cash is $1 (at the $40 close). With only the second session's split bar (or only
        its all bar) missing, the loop took the $20 close of e as the dividend's previous close and booked $0.50; the
        close immediately before the ex-date is unknown, so the cash is undefined and the trade is excluded."""
        cal = synth.calendar()
        s = cal.range("2020-06-01", "2020-06-12")
        e, x = s[1], s[5]
        closes = {s[0]: 20.0, s[1]: 20.0, s[2]: 40.0}

        def build():
            return synth.series(cal, s[0], s[-1], lambda d: closes.get(d, 39.0), cash_at={s[3]: 1.0})
        raw, split, allc = build()
        self.assertAlmostEqual(costs.cash_term(cal, raw, split, allc, e, x), 1.0, places=9)
        raw, split, allc = build()
        del split[s[2]]
        self.assertIsNone(costs.cash_term(cal, raw, split, allc, e, x))
        raw, split, allc = build()
        allc[s[2]] = {**allc[s[2]], "c": None}
        self.assertIsNone(costs.cash_term(cal, raw, split, allc, e, x))
        # the trade path books it as an undefined cash term, never as $0.50
        from core import trades
        raw, split, allc = build()
        del split[s[2]]
        self.assertIsNone(trades._cash(cal, {"raw": raw, "split": split, "all": allc}, e, x, 1.0))

    def test_cash_does_not_move_with_prices_after_the_ex_date(self):
        """Review round 14, Codex P2: entry close $20, a $1 dividend ex on x, an overnight exit at x's open. D7's
        formula booked cash 1 with x's close at 19 and cash 2 with x's close at 38; the cash is 1 either way."""
        cal = synth.calendar()
        s = cal.range("2020-06-01", "2020-06-05")
        e, x = s[1], s[2]
        for close_x in (19.0, 38.0):
            raw, split, allc = synth.series(cal, s[0], s[-1], lambda d: 20.0 if d < x else close_x,
                                            cash_at={x: 1.0})
            self.assertAlmostEqual(costs.cash_term(cal, raw, split, allc, e, x), 1.0, places=9)

    def test_the_trade_path_books_the_per_ex_date_cash(self):
        """trades._cash is the cash term of core.costs.cash_term, not D7's raw_c(e) x all_c(x) / all_c(e) - F x
        raw_c(x): with a $1 dividend ex on x and x's close at $38, D7's formula books $2; the booked cash is $1."""
        from core import trades
        cal = synth.calendar()
        s = cal.range("2020-06-01", "2020-06-05")
        e, x = s[1], s[2]
        for close_x in (19.0, 38.0):
            raw, split, allc = synth.series(cal, s[0], s[-1], lambda d: 20.0 if d < x else close_x,
                                            cash_at={x: 1.0})
            ev = {"raw": raw, "split": split, "all": allc}
            self.assertAlmostEqual(trades._cash(cal, ev, e, x, 1.0), 1.0, places=9)
        self.assertEqual(trades._cash(cal, ev, e, e, 1.0), 0.0)

    def test_cash_band_is_symmetric(self):
        # 5e-4 adjustment noise of either sign books 0 (review round 8, E6); a 5e-3 step books with its sign
        cal = synth.calendar()
        s = cal.range("2020-06-01", "2020-06-05")
        bar = lambda c: {"o": c, "h": c, "l": c, "c": c, "v": 1}  # noqa: E731
        raw = {d: bar(10.0) for d in s}
        for eps, want in ((5e-4, 0.0), (-5e-4, 0.0), (-5e-3, 10.0 * (1 - 1 / (1 - 5e-3)))):
            allc = {d: bar(10.0 * (1 + eps) if d == s[3] else 10.0) for d in s}
            self.assertAlmostEqual(costs.cash_term(cal, raw, raw, allc, s[1], s[3]), want, places=12)


if __name__ == "__main__":
    unittest.main()
