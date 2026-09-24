"""Deflated Sharpe ratio and CSCV PBO: published example, synthetic fixtures and receipt replay."""
import importlib.util
import itertools
import json
import math
from pathlib import Path
import random
import statistics
import unittest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "blueprints/us-equities/overfitting-controls"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


of = load("overfitting_controls_under_test", HERE / "overfitting.py")


def brute_force_pbo(matrix, partitions, metric):
    """Independent direct recomputation: concatenate rows, statistics module, explicit ranks."""
    t = len(matrix)
    size = t // partitions
    used = matrix[t - size * partitions:]
    blocks = [used[b * size:(b + 1) * size] for b in range(partitions)]
    n = len(matrix[0])

    def score(rows, c):
        col = [r[c] for r in rows]
        mean = statistics.fmean(col)
        if metric == "mean":
            return mean
        std = statistics.pstdev(col)
        return 0.0 if std == 0 else mean / std

    logits = []
    for chosen in itertools.combinations(range(partitions), partitions // 2):
        train = [r for b in chosen for r in blocks[b]]
        test = [r for b in range(partitions) if b not in chosen for r in blocks[b]]
        is_scores = [score(train, c) for c in range(n)]
        oos = [score(test, c) for c in range(n)]
        best = max(range(n), key=lambda c: (is_scores[c], -c))
        below = sum(v < oos[best] for v in oos)
        equal = sum(v == oos[best] for v in oos)
        rank = below + (equal + 1) / 2.0
        omega = rank / (n + 1)
        logits.append(math.log(omega / (1 - omega)))
    return logits


class DeflatedSharpeTests(unittest.TestCase):
    def test_published_numerical_example(self):
        # Bailey and Lopez de Prado (2014), numerical example: N = 100 independent
        # trials, annualized V[SR_n] = 1/2, selected annualized SR = 2.5, T = 1250
        # daily observations (250 per year), skewness -3, kurtosis 10. The paper
        # reports SR0 ~= 0.1132 (non-annualized) and DSR ~= 0.9004.
        sr0_annual = of.expected_max_sharpe(100, 0.5)
        sr0 = sr0_annual / math.sqrt(250)
        self.assertAlmostEqual(sr0, 0.1132, places=4)
        dsr, benchmark = of.deflated_sharpe(2.5 / math.sqrt(250), 1250, -3.0, 10.0, 100, 0.5 / 250)
        self.assertAlmostEqual(benchmark, sr0, places=12)
        self.assertAlmostEqual(dsr, 0.9004, places=4)

    def test_psr_reduces_to_normal_case(self):
        sr, t = 0.1, 500
        self.assertAlmostEqual(of.probabilistic_sharpe(sr, t, 0.0, 3.0),
                               statistics.NormalDist().cdf(sr * math.sqrt(t - 1) / math.sqrt(1 + sr * sr / 2)), places=14)
        self.assertEqual(of.probabilistic_sharpe(0.2, 100, -1.0, 6.0, 0.2), 0.5)

    def test_negative_skew_and_fat_tails_lower_psr(self):
        normal = of.probabilistic_sharpe(0.1, 250, 0.0, 3.0)
        self.assertLess(of.probabilistic_sharpe(0.1, 250, -2.0, 3.0), normal)
        self.assertLess(of.probabilistic_sharpe(0.1, 250, 0.0, 12.0), normal)

    def test_expected_max_matches_order_statistic_tables(self):
        # Expected maximum of N iid standard normals (Harter 1961): N=100 -> 2.50759.
        # The paper's approximation is asymptotic; allow 1.5% at N=100.
        self.assertAlmostEqual(of.expected_max_sharpe(100, 1.0) / 2.50759, 1.0, delta=0.015)
        self.assertEqual(of.expected_max_sharpe(1, 4.0), 0.0)
        self.assertGreater(of.expected_max_sharpe(1000, 1.0), of.expected_max_sharpe(100, 1.0))
        with self.assertRaises(ValueError):
            of.expected_max_sharpe(0, 1.0)

    def test_more_trials_deflate_more(self):
        first, _ = of.deflated_sharpe(0.1, 500, 0.0, 3.0, 2, 0.01)
        second, _ = of.deflated_sharpe(0.1, 500, 0.0, 3.0, 50, 0.01)
        self.assertLess(second, first)

    def test_moments_and_degenerate_series(self):
        m = of.moments([1.0, 2.0, 3.0, 4.0])
        self.assertAlmostEqual(m["std"], statistics.pstdev([1, 2, 3, 4]), places=14)
        self.assertAlmostEqual(m["skew"], 0.0, places=14)
        self.assertAlmostEqual(m["kurtosis"], 1.64, places=12)
        self.assertEqual(of.sharpe([0.0, 0.0, 0.0]), 0.0)
        with self.assertRaises(ValueError):
            of.sharpe([1.0, 1.0])
        with self.assertRaises(ValueError):
            of.moments([1.0])


class PboTests(unittest.TestCase):
    def test_reversal_is_fully_overfit(self):
        # Two blocks: trial 0 wins block 0, trial 1 wins block 1. Whichever block is
        # in-sample, the in-sample winner is last out of sample.
        matrix = [[1.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 1.0]]
        result = of.cscv_pbo(matrix, partitions=2)
        self.assertEqual(result["combinations"], 2)
        self.assertEqual(result["pbo"], 1.0)
        self.assertAlmostEqual(result["lambda_max"], math.log(0.5), places=14)

    def test_dominant_trial_is_not_overfit(self):
        rng = random.Random(7)
        matrix = [[rng.gauss(0, 1) + 10.0] + [rng.gauss(0, 1) for _ in range(5)] for _ in range(160)]
        result = of.cscv_pbo(matrix, partitions=8)
        self.assertEqual(result["combinations"], math.comb(8, 4))
        self.assertEqual(result["pbo"], 0.0)
        self.assertEqual(result["in_sample_selection_counts"][0], result["combinations"])
        self.assertEqual(result["probability_oos_loss"], 0.0)

    def test_pure_noise_is_near_one_half(self):
        pbos = []
        for seed in range(20):
            rng = random.Random(seed)
            matrix = [[rng.gauss(0, 1) for _ in range(10)] for _ in range(200)]
            pbos.append(of.cscv_pbo(matrix, partitions=10)["pbo"])
        self.assertAlmostEqual(statistics.fmean(pbos), 0.5, delta=0.1)

    def test_block_merge_equals_direct_recomputation(self):
        rng = random.Random(11)
        matrix = [[rng.gauss(0.001 * c, 0.02) for c in range(4)] + [0.0] for _ in range(103)]
        for metric in ("mean", "sharpe"):
            fast = of.cscv_pbo(matrix, partitions=8, metric=metric)
            slow = brute_force_pbo(matrix, 8, metric)
            self.assertEqual(fast["rows_dropped_earliest"], 103 - 8 * 12)
            self.assertEqual(len(slow), fast["combinations"])
            for a, b in zip(fast["logits"], slow):
                self.assertAlmostEqual(a, b, places=12)
            self.assertEqual(fast["pbo"], sum(x <= 0 for x in slow) / len(slow))

    def test_ties_use_average_rank_and_first_in_sample(self):
        matrix = [[0.0, 0.0, 0.0] for _ in range(8)]
        result = of.cscv_pbo(matrix, partitions=4)
        self.assertEqual(result["in_sample_selection_counts"], [6, 0, 0])
        self.assertEqual(result["lambda_zero_count"], 6)
        self.assertEqual(result["pbo"], 1.0)
        self.assertEqual(result["pbo_strict"], 0.0)

    def test_rejects_invalid_configuration(self):
        for args in ([[1.0, 2.0]] * 8, 3), ([[1.0]] * 8, 2), ([[1.0, 2.0]] * 3, 2), ([[1.0, float("nan")]] * 8, 2):
            with self.assertRaises(ValueError):
                of.cscv_pbo(*args)


class RetainedLedgerReplayTests(unittest.TestCase):
    def test_receipt_results_replay_from_retained_ledger(self):
        receipt = json.loads((HERE / "receipt.json").read_text())
        runner = load("overfitting_controls_runner", HERE / "evaluate.py")
        replay = runner.compute()

        def close(a, b, where):
            if isinstance(a, dict):
                self.assertEqual(sorted(a), sorted(b), where)
                for k in a:
                    close(a[k], b[k], where + "/" + k)
            elif isinstance(a, list):
                self.assertEqual(len(a), len(b), where)
                for i, (x, y) in enumerate(zip(a, b)):
                    close(x, y, "%s/%d" % (where, i))
            elif isinstance(a, float) and isinstance(b, float):
                self.assertTrue(math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12), where)
            else:
                self.assertEqual(a, b, where)

        close(replay, receipt["results"], "results")


if __name__ == "__main__":
    unittest.main()
