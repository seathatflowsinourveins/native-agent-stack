"""SYN: freeze guard, cost-table helpers and statistics of the ORB replication (sota-mover/orb).

Synthetic inputs only; no private data is read (every refusal happens before any file other than the
protocol is opened). Stdlib only (system python3).
"""
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ORB = Path(__file__).resolve().parents[1] / "blueprints/us-equities/sota-mover/orb"
if str(ORB) not in sys.path:
    sys.path.insert(0, str(ORB))


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, ORB / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


C = load("orb_common", "orb_common.py")
sys.modules["orb_common"] = C
E = load("orb_evaluate_under_test", "evaluate.py")
Q = load("orb_collect_quotes_under_test", "collect_quotes.py")
SIM = load("orb_simulate_under_test", "simulate.py")


def write_protocol(tmp, status, frozen):
    p = Path(tmp) / "protocol.json"
    p.write_text(json.dumps({"id": "x", "status": status, "frozen_before_outcomes": frozen}))
    return p, hashlib.sha256(p.read_bytes()).hexdigest()


class RefusalGuard(unittest.TestCase):
    def test_repository_protocol_is_a_draft(self):
        proto = json.loads((ORB / "protocol.json").read_text())
        self.assertEqual(proto["status"], "draft_pending_independent_pre_outcome_review")
        self.assertIs(proto["frozen_before_outcomes"], False)

    def test_require_frozen(self):
        with tempfile.TemporaryDirectory() as tmp:
            p, sha = write_protocol(tmp, "draft_pending_independent_pre_outcome_review", False)
            with self.assertRaises(SystemExit) as cm:
                C.require_frozen(p, None)
            self.assertIn("required", str(cm.exception.code))
            with self.assertRaises(SystemExit) as cm:
                C.require_frozen(p, sha)
            self.assertIn("status", str(cm.exception.code))
            p, sha = write_protocol(tmp, "frozen_before_outcomes", False)
            with self.assertRaises(SystemExit):
                C.require_frozen(p, sha)
            p, sha = write_protocol(tmp, "frozen_before_outcomes", True)
            with self.assertRaises(SystemExit) as cm:
                C.require_frozen(p, "0" * 64)
            self.assertIn("does not match", str(cm.exception.code))
            self.assertEqual(C.require_frozen(p, sha.upper())["id"], "x")

    def test_entry_points_refuse_on_the_draft(self):
        sha = hashlib.sha256((ORB / "protocol.json").read_bytes()).hexdigest()
        for main, args in ((E.main, ["run"]), (E.main, ["run", "--protocol-sha256", sha]),
                           (SIM.main, ["run", "--protocol-sha256", sha]), (SIM.main, ["run", "--population", "base"])):
            with self.assertRaises(SystemExit) as cm:
                main(args)
            self.assertTrue(str(cm.exception.code).startswith("refused"), args)


class QuoteHelpers(unittest.TestCase):
    def test_stamps(self):
        day = "2024-03-05"
        st = Q.stamps_for(day, 576, 960)
        self.assertEqual([(m, k) for _, m, k in st],
                         [(577, "trigger"), (592, "trigger+15m"), (637, "trigger+60m"), (955, "close-5m")])
        self.assertEqual(st[0][0], datetime(2024, 3, 5, 14, 37, tzinfo=timezone.utc).timestamp())  # 09:37 EST
        late = Q.stamps_for(day, 930, 960)
        self.assertEqual([k for _, _, k in late], ["trigger", "trigger+15m", "close-5m"])
        self.assertEqual([k for _, _, k in Q.stamps_for(day, 950, 960)], ["trigger", "close-5m"])

    def test_buckets_and_tiers(self):
        self.assertEqual(Q.time_bucket(576, 960), 0)
        self.assertEqual(Q.time_bucket(600, 960), 1)
        self.assertEqual(Q.time_bucket(955, 960), 3)
        self.assertEqual(Q.time_bucket(960, 960), 3)
        self.assertIsNone(Q.time_bucket(570, 960))
        self.assertEqual([Q.tier(x, Q.PRICE_TIERS) for x in (5.5, 20.0, 49.99, 200.0)], [0, 1, 1, 3])
        self.assertEqual([Q.tier(x, Q.LIQ_TIERS) for x in (5e7, 1e8, 6e8)], [0, 1, 2])

    def test_sample_key_is_deterministic(self):
        a = [Q.sample_key(f"S{i}", "2024-01-02", 1, 5) for i in range(500)]
        self.assertEqual(a, [Q.sample_key(f"S{i}", "2024-01-02", 1, 5) for i in range(500)])
        self.assertTrue(60 < sum(a) < 140)

    def test_rate_cap_after_0330_et(self):
        self.assertEqual(Q.allowed_per_minute(datetime(2026, 9, 25, 7, 29, tzinfo=timezone.utc)), 2000)  # 03:29 EDT
        self.assertEqual(Q.allowed_per_minute(datetime(2026, 9, 25, 7, 30, tzinfo=timezone.utc)), 500)   # 03:30 EDT

    def test_valid_quote_and_cells(self):
        qs = [{"bp": 10.0, "ap": 10.0}, {"bp": 0, "ap": 10.0}, {"bp": 9.99, "ap": 10.01}]
        self.assertEqual(Q.valid_quote(qs), qs[2])
        obs = [(0, 1, 2, 0.001)] * 40 + [(0, 1, 0, 0.003)] * 10 + [(2, 3, 1, 0.01)] * 5
        cells, p90 = Q.build_cells(obs)
        self.assertEqual(cells["0|1|2"]["source"], "cell")
        self.assertAlmostEqual(cells["0|1|2"]["half_spread"], 0.001)
        self.assertEqual(cells["0|1|0"]["source"], "time_x_price")   # 10 in the cell, 50 in time x price
        self.assertEqual(cells["2|3|1"]["source"], "table_p90")
        self.assertEqual(cells["2|3|1"]["half_spread"], p90)

    def test_cost_function_lookup(self):
        cells = {f"{t}|{p}|{l}": {"half_spread": t * 100 + p * 10 + l} for t in range(4) for p in range(4) for l in range(3)}
        hs = SIM.cost_function({"groups": {"post_publication": {"cells": cells}}}, "post_publication", 2, 960)
        self.assertEqual(hs(575, 30.0), 12)     # 09:35 bar ends 09:36: bucket 0; $30: tier 1; liquidity 2
        self.assertEqual(hs(959, 250.0), 332)


class SimulateHelpers(unittest.TestCase):
    def test_trade_record_gross_and_net(self):
        fees = json.loads((ORB.parents[1] / "mover-v3/data/fees-v3.json").read_text())
        bars = [(575, 12.0, 12.1, 11.95, 12.05, 1.0), (959, 12.6, 12.6, 12.6, 12.6, 1.0)]
        t = SIM.trade_record("F1", fees, "2024-06-03", 1, 12.0, 2.0, bars, 960, lambda m, p: 0.001)
        self.assertAlmostEqual(t["gross_R"], (12.6 - 12.0) / 0.2)            # base prices, before costs
        net = (12.6 * 0.999 - 12.0 * 1.001 - (27.8 * 12.6 * 0.999 / 1e6 + 0.000166)) / 0.2
        self.assertAlmostEqual(t["net_R"], net)
        self.assertIsNone(SIM.trade_record("F1", fees, "2024-06-03", 1, 13.0, 2.0, bars, 960, lambda m, p: 0.0))

    def test_ssr_flag(self):
        bars = [(570, 10, 10, 8.9, 9, 1), (576, 9, 9, 8.5, 8.6, 1)]
        self.assertEqual(SIM.ssr_flag(1, 5.0, 10.0, 10.0, 1.0, bars, 576), 0)        # longs never
        self.assertEqual(SIM.ssr_flag(-1, 8.9, 10.0, 10.0, 1.0, [], 576), 1)         # prior session -11%
        self.assertEqual(SIM.ssr_flag(-1, 9.5, 10.0, 10.0, 1.0, bars, 576), 1)       # 8.9 <= 9.0 before the trigger
        self.assertEqual(SIM.ssr_flag(-1, 9.5, 10.0, 10.0, 1.0, bars[1:], 576), 0)   # only at/after the trigger
        self.assertEqual(SIM.ssr_flag(-1, 9.5, 10.0, 20.0, 2.0, bars, 576), 1)       # prior close in post-split units


class Statistics(unittest.TestCase):
    def test_holm(self):
        h = E.holm({"a": 0.01, "b": 0.04, "c": 0.03}, 0.05)
        self.assertTrue(h["a"][1])
        self.assertFalse(h["c"][1])   # 0.03 > 0.05/2
        self.assertFalse(h["b"][1])
        self.assertAlmostEqual(h["a"][0], 0.03)
        self.assertAlmostEqual(h["c"][0], 0.06)
        self.assertAlmostEqual(h["b"][0], 0.06)

    def test_bootstrap_mean(self):
        mean, p, lo, hi = E.bootstrap_mean([10.0] * 50, [10] * 50, 200, 1)
        self.assertEqual((mean, lo, hi), (1.0, 1.0, 1.0))
        self.assertLess(p, 0.01)
        mean, p, lo, hi = E.bootstrap_mean([1.0, -1.0] * 50, [1] * 100, 500, 1)
        self.assertEqual(mean, 0.0)
        self.assertGreater(p, 0.3)
        self.assertLess(lo, 0.0)
        self.assertGreater(hi, 0.0)

    def test_power(self):
        self.assertGreater(E.n_required(0.08, 3.0, 1.0, 0.05 / 3), E.n_required(0.08, 2.0, 1.0, 0.05 / 3))
        self.assertAlmostEqual(E.mde(E.n_required(0.08, 2.0, 1.3, 0.05 / 3), 2.0, 1.3, 0.05 / 3), 0.08, places=3)

    def test_portfolio_paper_sizing(self):
        fees = json.loads((ORB.parents[1] / "mover-v3/data/fees-v3.json").read_text())
        t = {"d": "2024-06-03", "entry_fill": 10.0, "exit_fill": 10.4, "atr14": 2.0, "dirn": 1, "slots": 20}
        stats, rets = E.portfolio([t], ["2024-06-03", "2024-06-04"], fees, "F0", "paper")
        # 62.5 shares x $0.40 - 2 x 0.0035 x 62.5 commission
        self.assertAlmostEqual(rets[0], (62.5 * 0.4 - 0.4375) / 25000)
        self.assertEqual(rets[1], 0.0)
        self.assertEqual(stats["trades"], 1)
        stats1, rets1 = E.portfolio([t], ["2024-06-03"], fees, "F1", "1x")
        self.assertAlmostEqual(rets1[0], (125 * 0.4 - (27.8 * 1300 / 1e6 + 125 * 0.000166)) / 25000)


if __name__ == "__main__":
    unittest.main()
