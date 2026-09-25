"""Synthetic tests for protocol v2 families E (first-cross) and F (follow-up setups) (made-up bars)."""
import importlib.util
import sys
import unittest
from pathlib import Path

HAS_NUMPY = importlib.util.find_spec("numpy") is not None
HERE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/mover-early-entry"
DAY, PREV = "2023-03-15", "2023-03-14"


@unittest.skipUnless(HAS_NUMPY, "requires the pinned numpy runtime (protocol inputs.runtime)")
class FollowUp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(HERE))
        spec = importlib.util.spec_from_file_location("mover_fv2", HERE / "features_v2.py")
        cls.V = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.V)
        cls.R = cls.V.R

    def bar(self, hhmm, o, h, l, c, v=100_000):
        return (self.R.et_epoch(DAY, hhmm), o, h, l, c, v, c)

    def test_first_cross_takes_the_first_qualifying_bar(self):
        R = self.R
        rows = [self.bar("07:00", 10, 10, 10, 10), self.bar("07:10", 11, 11, 11, 11), self.bar("07:20", 12.1, 12.1, 12.1, 12.1),
                self.bar("07:30", 12.5, 12.5, 12.5, 12.5), self.bar("09:40", 13, 13, 13, 13)]
        b = R.Bars(*zip(*rows), day_start=R.et_epoch(DAY, "04:00"))
        ks = self.V.first_cross(b, DAY, 10.0, [], R.et_epoch(PREV, "16:00"))
        # bar 3 (07:30) is the first whose previous close (12.1) is >= +20%; dv before it = 3.31M
        self.assertEqual(ks["E|04:00-09:30|G0.20|V250000|any"], 3)
        self.assertEqual(ks["E|04:00-11:00|G0.20|V1000000|any"], 3)
        self.assertNotIn("E|04:00-11:00|G0.20|V5000000|any", ks)
        self.assertEqual(ks["E|09:30-11:00|G0.20|V250000|any"], 4)  # the regular-session window starts at 09:30
        self.assertNotIn("E|04:00-09:30|G0.20|V250000|news_before_t", ks)
        ks = self.V.first_cross(b, DAY, 10.0, [R.et_epoch(DAY, "07:28") + 30], R.et_epoch(PREV, "16:00"))
        self.assertEqual(ks["E|04:00-11:00|G0.20|V250000|news_before_t"], 4)  # 07:30 is < 120 s after the headline

    def test_orb_breakout_fill_and_exits_start_after_the_entry_bar(self):
        R = self.R
        rows = [self.bar("09:30", 12, 12.5, 11.8, 12.2), self.bar("09:34", 12.2, 12.6, 12.0, 12.4),
                self.bar("09:40", 12.5, 13.0, 11.5, 12.8),  # breaks 12.6; its low 11.5 is before or after the break: ignored (V2)
                self.bar("09:41", 12.8, 12.9, 11.9, 12.0),  # the range low 11.8 is not reached
                self.bar("09:42", 11.7, 11.7, 11.0, 11.2)]  # gap below the stop -> fill at the open
        b = R.Bars(*zip(*rows), day_start=R.et_epoch(DAY, "04:00"))
        found = self.V.setups(b, DAY)
        k, entry, stop, brk = found["F1_orb5"]
        self.assertEqual((k, entry, stop, brk), (2, 12.6, 11.8, True))
        ex, degen = self.V.y_exits(b, DAY, k, entry, stop, True, 12.0, R.et_epoch(DAY, "16:00"))
        self.assertEqual(ex["Y2"][0], 11.7)
        self.assertEqual(ex["Y4"][0], 11.7)
        self.assertFalse(degen)
        self.assertEqual(ex["Y1"][0], 12.0)

    def test_y3_trails_only_after_ten_percent(self):
        R = self.R
        rows = [self.bar("09:30", 10, 10, 10, 10), self.bar("09:31", 10, 11.2, 10, 11.1), self.bar("09:32", 11.0, 11.0, 10.0, 10.1)]
        b = R.Bars(*zip(*rows), day_start=R.et_epoch(DAY, "04:00"))
        ex, _ = self.V.y_exits(b, DAY, 0, 10.0, 9.0, False, 10.5, R.et_epoch(DAY, "16:00"))
        # running high 11.2 >= 11.0 -> level 0.9 x 11.2 = 10.08; bar 09:32 low 10.0 -> exit at min(10.08, 11.0)
        self.assertAlmostEqual(ex["Y3"][0], 10.08)


@unittest.skipUnless(HAS_NUMPY, "requires the pinned numpy runtime (protocol inputs.runtime)")
class FollowUpSetups(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        FollowUp.setUpClass.__func__(cls)

    def bar(self, hhmm, o, h, l, c, v=100_000):
        return (self.R.et_epoch(DAY, hhmm), o, h, l, c, v, c)

    def day_record(self, rows, open_px, close_px=13.0, ref=10.0):
        auc = {PREV: {"o": [], "c": [{"c": "6", "p": ref, "s": 100, "x": "Q"}]},
               DAY: {"o": [{"c": "O", "p": open_px, "s": 100, "x": "Q"}] if open_px else [], "c": [{"c": "6", "p": close_px, "s": 100, "x": "Q"}]}}
        return self.V.symbol_day_v2(DAY, "AAAA", PREV, False, False, rows, auc, [], {"raw_c": close_px})

    def test_f3_waits_for_0931_and_stops_at_ninety_percent_of_the_open(self):
        rows = [self.bar("08:00", 12, 12.5, 12, 12.4, 50_000), self.bar("09:30", 12.6, 12.9, 12.5, 12.8),
                self.bar("09:31", 12.8, 13.2, 12.7, 13.1), self.bar("09:32", 13.1, 13.3, 11.0, 11.2)]
        rec = self.day_record(rows, open_px=12.6)
        f3 = rec["F"]["F3_premarket_high_break"]
        self.assertEqual(f3["entry_ts"], self.R.et_epoch(DAY, "09:31"))  # the 09:30 bar is not an entry bar (V16)
        self.assertAlmostEqual(f3["entry"], 12.8)  # max(open 12.8, pre-market high 12.5)
        self.assertAlmostEqual(f3["stop"], 0.9 * 12.6)
        self.assertAlmostEqual(f3["exits"]["Y2"][0], 0.9 * 12.6)  # the 09:32 low reaches the stop

    def test_no_official_open_is_counted_and_degenerate_stops_exit_next_bar(self):
        rows = [self.bar("08:00", 12, 12.5, 12, 12.4, 50_000), self.bar("09:31", 12.8, 13.2, 12.7, 13.1)]
        rec = self.day_record(rows, open_px=None)
        self.assertTrue(rec["f_candidate_no_official_open"])
        self.assertEqual(rec["F"], {})
        b = self.R.Bars(*zip(*[self.bar("09:40", 10, 10.5, 9.9, 10.2), self.bar("09:41", 10.4, 10.6, 10.3, 10.5)]), day_start=self.R.et_epoch(DAY, "04:00"))
        ex, degen = self.V.y_exits(b, DAY, 0, 10.0, 10.1, False, 11.0, self.R.et_epoch(DAY, "16:00"))
        self.assertTrue(degen)
        self.assertEqual(ex["Y2"][0], 10.4)
        self.assertEqual(ex["Y3"], ex["Y4"])
        self.assertEqual(ex["Y1"][0], 11.0)

    def test_vwap_reclaim_entry_and_stop(self):
        rows = [self.bar("09:30", 12, 12.2, 11.9, 12.0), self.bar("09:35", 12.0, 12.0, 11.0, 11.2),  # dip below VWAP
                self.bar("09:36", 11.2, 12.5, 11.2, 12.4),  # reclaim (close above VWAP)
                self.bar("09:37", 12.4, 12.6, 12.3, 12.5)]
        b = self.R.Bars(*zip(*rows), day_start=self.R.et_epoch(DAY, "04:00"))
        vol = [r[5] for r in rows]
        k, entry, stop, brk = self.V.vwap_reclaim(b, DAY, __import__("numpy").array(vol, dtype=float))
        self.assertEqual((k, entry, stop, brk), (3, 12.4, 11.0, False))

    def test_holdout_gate_refuses_v1_results_and_other_cost_tables(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            fake_table = Path(tmp) / "t.json"
            fake_table.write_text("{}")
            with self.assertRaises(SystemExit):
                self.V.main(["--daily", str(fake_table), "--split", "dev", "--cost-table", str(fake_table), "--out", str(Path(tmp) / "o")])
            v1 = Path(tmp) / "v1.json"
            v1.write_text(json.dumps({"stage": "dev_val", "protocol": "mover-early-entry-v1-20260924",
                                      "inputs": {"cost_table_sha256": self.V.V1_COST_TABLE_SHA256}}))
            table = HERE / "evidence/cost-table-run-v1.json"
            with self.assertRaises(SystemExit) as cm:
                self.V.main(["--daily", str(fake_table), "--split", "holdout", "--cost-table", str(table), "--dev-val", str(v1), "--out", str(Path(tmp) / "o")])
            self.assertIn("v2 dev_val", str(cm.exception))


@unittest.skipUnless(HAS_NUMPY and importlib.util.find_spec("duckdb") is not None, "requires the pinned numpy and duckdb runtime")
class PrePositioning(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(HERE))
        spec = importlib.util.spec_from_file_location("mover_ev2", HERE / "evaluate_v2.py")
        cls.E = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.E)

    def test_calendar_adjacency_gap_hold_and_forced_loss(self):
        import duckdb
        import tempfile
        cal = [f"2023-03-{d:02d}" for d in (1, 2, 3, 6, 7, 8, 9, 10, 13, 14, 15, 16)]
        rows = []
        # AAAA: +40% on 03-03 closing at its high (S1), next day normal
        # BBBB: +40% on 03-03, next row only on 03-08 (3 sessions later: held through the gap)
        # CCCC: +40% on 03-03, never trades again within 5 sessions (forced -100%)
        for sym, days in (("AAAA", cal), ("BBBB", cal[:3] + cal[5:]), ("CCCC", cal[:3] + cal[10:])):
            for d in days:
                c = 14.0 if d == "2023-03-03" else 10.0
                rows.append((sym, d, c, c, c, c, 1_000_000.0, c, c, c, c, c, 1_000_000.0, True, True))
        with tempfile.TemporaryDirectory() as tmp:
            pq = Path(tmp) / "daily.parquet"
            con = duckdb.connect()
            con.execute("""CREATE TABLE t (symbol VARCHAR, session_date DATE, raw_o DOUBLE, raw_h DOUBLE, raw_l DOUBLE, raw_c DOUBLE,
                           raw_v DOUBLE, raw_vw DOUBLE, all_o DOUBLE, all_h DOUBLE, all_l DOUBLE, all_c DOUBLE, all_v DOUBLE, in_raw BOOLEAN, in_all BOOLEAN)""")
            con.executemany("INSERT INTO t VALUES (" + ",".join("?" * 15) + ")", rows)
            con.execute(f"COPY t TO '{pq}' (FORMAT PARQUET)")
            cells = {f"{tb}|{pt}|{dt}": {"half_spread": 0.001} for tb in range(4) for pt in range(4) for dt in range(3)}
            T, cap, skips = self.E.p_trades(pq, self.E.V1.Costs({"cells": cells}), cal, cal[1:9], cal[1], cal[8])
        s1 = [i for i, r in enumerate(T.rid) if r == "P|S1_day2_runner|Z2"]
        by_sym = {T.symbol[i]: i for i in s1}
        self.assertEqual(sorted(by_sym), ["AAAA", "BBBB", "CCCC"])
        self.assertEqual(T.flag[by_sym["AAAA"]], "")
        self.assertEqual(T.flag[by_sym["BBBB"]], "held_through_gap")
        self.assertEqual(T.flag[by_sym["CCCC"]], "no_row_within_5_sessions")
        self.assertEqual(T.net["primary"][by_sym["CCCC"]], -1.0)
        self.assertAlmostEqual(T.exit[by_sym["AAAA"]] / T.entry[by_sym["AAAA"]], 10.0 / 14.0)
        self.assertEqual(skips.get("previous_row_not_the_previous_session", 0), 1)  # BBBB on 03-08 (its previous row is 03-03)


if __name__ == "__main__":
    unittest.main()
