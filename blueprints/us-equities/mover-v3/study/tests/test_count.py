"""chronology.holdout.count_unit: exactly the six integer keys, no price or return function on the count path,
and the extension decision (count_unit is used only for it, R8-8)."""
import unittest
from unittest import mock

from core import costs, count_unit, fills
from core.records import ts_epoch
from core.store import Store
from core.trades import Ctx
from tests import synth
from tests.test_trades import CELLS, FEES, book, make_event


def serve_count(events, ctx, terc, quotes):
    store = Store()
    for _ in range(20):
        out = count_unit.count(events, ctx, store, terc)
        if "needs" not in out:
            return out, store
        for req in out["needs"]:
            sym = req["params"]["symbols"]
            lo, hi = ts_epoch(req["params"]["start"]), ts_epoch(req["params"]["end"])
            synth.put_quotes(store, req, sym, [q for q in quotes.get(sym, []) if lo <= q["t"] <= hi])
    raise AssertionError


class CountUnit(unittest.TestCase):
    def setUp(self):
        self.cal = synth.calendar("2026-06-01", "2028-06-30")
        self.n0 = "2026-11-23"
        seg = (self.n0, self.cal.offset(self.n0, 251))
        self.ctx = Ctx(cal=self.cal, stage="holdout", segs=[seg], fees=costs.Fees(FEES, cal=self.cal), cells=CELLS, mode="count")

    def _events(self):
        cal = self.cal
        out, quotes, terc = [], {}, {}
        for i, (sym, t, tc) in enumerate((("AAA", "2026-12-01", "high"), ("BBB", "2026-12-01", "low"),
                                          ("CCC", "2027-01-05", None), ("DDD", "2027-02-01", "low"))):
            ev = make_event(cal, t, sym=sym)
            out.append(ev)
            terc[(sym, t)] = tc
            d1 = cal.offset(t, 1)
            quotes[sym] = [book(cal, d1, "09:35"), book(cal, d1, "15:55")] if sym != "DDD" else []
        return out, terc, quotes

    def test_keys_are_exactly_the_six_integers(self):
        evs, terc, quotes = self._events()
        out, _ = serve_count(evs, self.ctx, terc, quotes)
        self.assertEqual(set(out), set(count_unit.KEYS))
        self.assertTrue(all(type(v) is int for v in out.values()))
        self.assertEqual(out, {"H1-D:high": 1, "H1-D:low": 1, "H1-D-b_lane-low": 1, "H3-a": 3, "H3-b": 3, "H3-c": 4})

    def test_count_path_calls_no_price_or_return_function(self):
        evs, terc, quotes = self._events()
        boom = mock.Mock(side_effect=AssertionError("price function called on the count path"))
        with mock.patch.object(fills, "mid", boom), mock.patch.object(fills, "half_spread", boom), \
                mock.patch.object(costs, "trade_net_return", boom), mock.patch.object(costs, "cash_term", boom), \
                mock.patch.object(costs, "per_side", boom), mock.patch.object(costs, "impact", boom), \
                mock.patch.object(costs, "cell_key", boom):
            out, store = serve_count(evs, self.ctx, terc, quotes)
        self.assertEqual(out["H3-a"], 3)
        self.assertTrue(all(r["kind"] == "quote_entry" for r in store.req.values()))  # no exit window is fetched

    def test_count_mode_is_required(self):
        with self.assertRaises(ValueError):
            count_unit.count([], Ctx(cal=self.cal, stage="holdout", segs=[], mode="read"), Store(), {})

    def test_extension_decision(self):
        c = {"H1-D:high": 120, "H1-D:low": 90, "H1-D-b_lane-low": 90, "H3-a": 400, "H3-b": 149, "H3-c": 500}
        self.assertEqual(count_unit.extension_decision(c, ("H3-a",), 0)["extend"], False)
        d = count_unit.extension_decision(c, ("H1-D", "H3-a", "H3-b"), 0)
        self.assertEqual((d["extend"], d["below_minimum"]), (True, ["H1-D", "H3-b"]))
        d = count_unit.extension_decision(c, ("H1-D",), 2)
        self.assertEqual((d["extend"], d["underpowered"]), (False, ["H1-D"]))


if __name__ == "__main__":
    unittest.main()
