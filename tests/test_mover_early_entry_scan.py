"""Synthetic tests for the live mover scanner (made-up symbols and prices; no network)."""
import importlib.util
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

HAS_NUMPY = importlib.util.find_spec("numpy") is not None
HERE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/mover-early-entry"


@unittest.skipUnless(HAS_NUMPY, "requires the pinned numpy runtime (protocol inputs.runtime)")
class Scanner(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(HERE))
        spec = importlib.util.spec_from_file_location("mover_scan_mod", HERE / "mover_scan.py")
        cls.S = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.S)
        cls.R = cls.S.R

    def fake(self, day="2026-03-18"):
        R = self.R
        prev = "2026-03-17"

        def bar(hhmm, c, v, vw=None):
            return {"t": datetime.fromtimestamp(R.et_epoch(day, hhmm), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "o": c, "h": c, "l": c, "c": c, "v": v, "vw": vw or c}

        spy = [{"t": (datetime(2025, 1, 2) + timedelta(days=i)).strftime("%Y-%m-%dT05:00:00Z"), "c": 500 + (i % 7)} for i in range(300)]
        data = {
            "/v2/assets": [{"symbol": s, "tradable": True, "exchange": "NASDAQ"} for s in ("AAAA", "BBBB", "CCCC", "DDDDW", "EEEE")]
                          + [{"symbol": "OTCX", "tradable": True, "exchange": "OTC"}],
            "snapshots": {"AAAA": {"latestTrade": {"p": 2.6}, "prevDailyBar": {"c": 2.0, "t": f"{prev}T04:00:00Z"}},
                          "BBBB": {"latestTrade": {"p": 12.5}, "prevDailyBar": {"c": 10.0, "t": f"{prev}T04:00:00Z"}},
                          "CCCC": {"latestTrade": {"p": 5.1}, "prevDailyBar": {"c": 5.0, "t": f"{prev}T04:00:00Z"}},
                          "EEEE": {"latestTrade": {"p": 0.9}, "prevDailyBar": {"c": 0.5, "t": f"{prev}T04:00:00Z"}}},
            "bars1m": {"AAAA": [bar("07:10", 2.4, 200_000), bar("07:59", 2.6, 100_000)],
                       "BBBB": [bar("07:30", 12.4, 30_000), bar("08:00", 99.0, 1)]},
            "auctions": {"AAAA": [{"d": prev, "o": [{"c": "O", "p": 1.9, "s": 100, "x": "Q"}], "c": [{"c": "6", "p": 2.0, "s": 500, "x": "Q"}]}],
                         "BBBB": [{"d": prev, "o": [{"c": "O", "p": 9.9, "s": 100, "x": "Q"}], "c": [{"c": "6", "p": 10.0, "s": 500, "x": "Q"}]}]},
            "daily": {"raw": {"AAAA": 2.0, "BBBB": 10.0}, "split": {"AAAA": 2.0, "BBBB": 10.0}},
            "spy": spy,
        }

        class Fake:
            def get(self, base, path, params):
                if path == "/v2/calendar":
                    yield [{"date": d} for d in ("2026-03-16", prev, day)]
                elif path == "/v1/corporate-actions":
                    yield {"corporate_actions": {}}
                elif path == "/v2/assets":
                    yield data["/v2/assets"]
                elif path == "/v2/stocks/snapshots":
                    yield {s: data["snapshots"][s] for s in params["symbols"].split(",") if s in data["snapshots"]}
                elif path == "/v2/stocks/bars" and params["timeframe"] == "1Min":
                    yield {"bars": {s: data["bars1m"].get(s, []) for s in params["symbols"].split(",")}}
                elif path == "/v2/stocks/bars" and params.get("symbols") == "SPY":
                    yield {"bars": {"SPY": data["spy"]}}
                elif path == "/v2/stocks/bars":
                    adj = params["adjustment"]
                    yield {"bars": {s: [{"c": data["daily"][adj][s]}] for s in params["symbols"].split(",") if s in data["daily"][adj]}}
                elif path == "/v2/stocks/auctions":
                    yield {"auctions": {s: data["auctions"].get(s, []) for s in params["symbols"].split(",")}}
                elif path == "/v1beta1/news":
                    yield {"news": []}
                else:
                    raise AssertionError(path)
        return Fake()

    def test_scan_applies_the_historical_rule_and_ranks_by_dollar_volume(self):
        now = datetime.fromtimestamp(self.R.et_epoch("2026-03-18", "08:00") + 5, timezone.utc)
        out = self.S.scan(self.fake(), "08:00|G0.20|V250000|any", now)
        # AAAA: 2.6 / 2.0 - 1 = 30%, dv = 2.4 x 200k + 2.6 x 100k = 740k -> fires.
        # BBBB: the 08:00 bar is not before t; 12.4 / 10 = +24% but dv 372k -> fires; CCCC is below the prefilter.
        self.assertEqual([c["symbol"] for c in out["candidates"]], ["AAAA", "BBBB"])
        self.assertAlmostEqual(out["candidates"][0]["gain_at_t"], 0.30)
        self.assertEqual(out["universe"], 4)  # OTC and the likely warrant are excluded
        self.assertEqual(out["prefiltered"], 2)
        self.assertIn(out["regime_factor"], (0.5, 1.0))
        # A higher dollar-volume floor removes BBBB; the 1M floor removes both.
        self.assertEqual(self.S.scan(self.fake(), "08:00|G0.20|V1000000|any", now)["fired"], 0)
        self.assertEqual([c["symbol"] for c in self.S.scan(self.fake(), "08:00|G0.30|V250000|any", now)["candidates"]], ["AAAA"])

    def test_the_0930_rule_waits_for_its_signal_cutoff(self):
        at = datetime.fromtimestamp(self.R.et_epoch("2026-03-18", "09:28") - 5, timezone.utc)
        with self.assertRaises(SystemExit):
            self.S.scan(self.fake(), "09:30|G0.20|V250000|any", at)
        ok = datetime.fromtimestamp(self.R.et_epoch("2026-03-18", "09:28") + 2, timezone.utc)
        self.assertEqual(self.S.scan(self.fake(), "09:30|G0.20|V250000|any", ok)["prev_session"], "2026-03-17")

    def test_scan_refuses_before_the_rule_time_and_news_variant_needs_headlines(self):
        early = datetime.fromtimestamp(self.R.et_epoch("2026-03-18", "08:00") - 5, timezone.utc)
        with self.assertRaises(SystemExit):
            self.S.scan(self.fake(), "08:00|G0.20|V250000|any", early)
        now = datetime.fromtimestamp(self.R.et_epoch("2026-03-18", "08:00") + 5, timezone.utc)
        self.assertEqual(self.S.scan(self.fake(), "08:00|G0.20|V250000|news_before_t", now)["fired"], 0)


if __name__ == "__main__":
    unittest.main()
