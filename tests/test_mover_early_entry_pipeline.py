"""End-to-end synthetic run of the mover early-entry pipeline: features -> entries -> metrics (no private data)."""
import importlib.util
import sys
import unittest
from pathlib import Path

HAS_NUMPY = importlib.util.find_spec("numpy") is not None
HERE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/mover-early-entry"


def load(name):
    sys.path.insert(0, str(HERE))
    spec = importlib.util.spec_from_file_location(f"mover_pipe_{name}", HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@unittest.skipUnless(HAS_NUMPY, "requires the pinned numpy runtime (protocol inputs.runtime)")
class Pipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.F = load("features")
        cls.E = load("evaluate")
        cls.R = cls.F.R

    def session_rows(self, day, prev, k):
        R = self.R
        rows = []
        for j, sym in enumerate(("AAAA", "BBBB", "CCCC")):
            ref = 2.0 + j
            bars = []
            for m in range(4 * 60, 16 * 60, 5):  # a bar every 5 minutes, 04:00-15:55
                hh, mm = divmod(m, 60)
                drift = 1.35 if m < 9 * 60 + 30 else (1.35 + 0.001 * ((m + k + j) % 50) - 0.02)
                px = round(ref * drift, 4)
                bars.append((R.et_epoch(day, f"{hh:02d}:{mm:02d}"), px, px * 1.01, px * 0.99, px, 50_000, px))
            auc = {prev: {"o": [], "c": [{"c": "6", "p": ref, "s": 1000, "x": "Q"}]},
                   day: {"o": [{"c": "O", "p": ref * 1.34, "s": 5000, "x": "Q"}], "c": [{"c": "6", "p": ref * 1.3, "s": 9000, "x": "Q"}]}}
            rec = self.F.symbol_day(day, sym, prev, False, bars, auc, [R.et_epoch(prev, "18:00")], {}, True)
            rec["supplement"] = j == 2
            rows.append(rec)
        return rows

    def test_pipeline_runs_and_is_deterministic(self):
        cal = [f"2023-03-{d:02d}" for d in (1, 2, 3, 6, 7, 8, 9, 10, 13, 14)]
        rows = []
        for k, day in enumerate(cal):
            prev = cal[k - 1] if k else "2023-02-28"
            rows.extend(self.session_rows(day, prev, k))
        self.assertTrue(all(r["t"]["07:00"]["loosest"] for r in rows))
        cells = {f"{tb}|{pt}|{dt}": {"half_spread": 0.005} for tb in range(4) for pt in range(4) for dt in range(3)}
        costs = self.E.Costs({"cells": cells})
        regime = {d: 1.0 for d in cal}
        E1 = self.E.Entries(rows, costs, {}, cal)
        out1 = self.E.evaluate_split(E1, regime)
        E2 = self.E.Entries(rows, costs, {}, cal)
        out2 = self.E.evaluate_split(E2, regime)
        self.assertEqual(out1, out2)
        rid = "07:00|G0.20|V250000|any|X1"
        m = out1[rid]
        self.assertEqual(m["trades"], 30)
        self.assertEqual(m["without_premarket_supplement_rows"][0], 20)
        # entry at 07:00 near 1.35 x ref, official close 1.30 x ref -> a loss before costs
        self.assertLess(m["gross_mean"], 0)
        self.assertLess(m["mean"], m["gross_mean"])
        self.assertGreater(m["p"], 0.5)
        self.assertIn("1", m["portfolio"])
        cap = self.E.capture(rows)
        self.assertIn("07:00|G0.20|V250000|any", cap)
        self.assertEqual(cap["07:00|G0.20|V250000|any"]["0.30-0.50"]["fired"], 30)
        rep = self.E.replication(rows)
        self.assertEqual(rep["tier_ge_1_symbol_days"], 0)


if __name__ == "__main__":
    unittest.main()
