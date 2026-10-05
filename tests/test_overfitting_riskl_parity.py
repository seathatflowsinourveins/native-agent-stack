"""Optional synthetic parity checks against the installed RiskLabAI 3.2.0.

Source: RiskLabAI/RiskLabAI.py, 7d5aa11271c70d83a7069d5900d80bb08b29e481,
src/RiskLabAI/backtest/{probabilistic_sharpe_ratio,
probability_of_backtest_overfitting,backtest_statistics,test_set_overfitting}.py
and backtest/validation/leakage_aware_hpo.py.
See docs/decisions/2026-10-05-overfitting-riskl-parity.md for line citations.
No install, network, retained-ledger replay or strategy gate runs here.
"""

import importlib.util
from importlib.metadata import PackageNotFoundError, version
import math
from pathlib import Path
import statistics
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_VERSION = "3.2.0"
REL_TOL = ABS_TOL = 1e-12
# expected_max_sharpe_ratio rounds Euler's constant to 0.5772156649 at
# test_set_overfitting.py:49. Its N=2 benchmark differs by about 2.66e-12.
BENCHMARK_REL_TOL = 1e-11

try:
    INSTALLED_VERSION = version("RiskLabAI")
except PackageNotFoundError:
    INSTALLED_VERSION = None

SKIP_REASON = f"optional RiskLabAI {REQUIRED_VERSION} is not installed"
UPSTREAM_AVAILABLE = False
if INSTALLED_VERSION == REQUIRED_VERSION:
    try:
        import numpy as np
        from RiskLabAI.backtest import expected_max_sharpe_ratio as risk_expected
        from RiskLabAI.backtest.validation import deflated_sharpe_gate as risk_dsr
        from RiskLabAI.backtest.backtest_statistics import sharpe_ratio as risk_sharpe
        from RiskLabAI.backtest.probabilistic_sharpe_ratio import (
            benchmark_sharpe_ratio as risk_benchmark,
            probabilistic_sharpe_ratio as risk_psr,
        )
        from RiskLabAI.backtest.probability_of_backtest_overfitting import (
            probability_of_backtest_overfitting as risk_pbo,
        )
    except ImportError as error:
        SKIP_REASON = f"optional RiskLabAI {REQUIRED_VERSION} is not importable: {error}"
    else:
        UPSTREAM_AVAILABLE = True
elif INSTALLED_VERSION is not None:
    SKIP_REASON = (
        f"parity requires RiskLabAI {REQUIRED_VERSION}; found {INSTALLED_VERSION}"
    )


def mean_metric(returns, risk_free_return):
    """Adapt the local mean metric to RiskLabAI's supported metric callback."""
    return float(np.mean(returns - risk_free_return))


# Fixed, divisible, nonconstant fixture. Small column offsets avoid mean ties.
REGULAR_MATRIX = (
    (8, 2.01, -0.98, 4.03),
    (-2, 6.01, 3.02, -3.97),
    (1, -6.99, 5.02, 2.03),
    (4, 3.01, -5.98, 1.03),
    (-3, 8.01, 2.02, -0.97),
    (7, -0.99, -3.98, 5.03),
    (-5, 4.01, 9.02, -1.97),
    (2, -2.99, 1.02, 8.03),
    (6, -4.99, 4.02, -2.97),
    (-4, 7.01, -1.98, 6.03),
    (3, 1.01, 8.02, -4.97),
    (-1, 5.01, -2.98, 7.03),
    (5, -1.99, 6.02, 3.03),
    (-6, 9.01, 1.02, -3.97),
    (9, -3.99, -4.98, 2.03),
    (0, 6.01, 3.02, -6.97),
)


@unittest.skipUnless(UPSTREAM_AVAILABLE, SKIP_REASON)
class RiskLabParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "overfitting_riskl_parity_local",
            ROOT / "blueprints/us-equities/overfitting-controls/overfitting.py",
        )
        cls.local = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.local)

    def assert_close(self, local, upstream, rel_tol=REL_TOL):
        self.assertTrue(
            math.isclose(local, upstream, rel_tol=rel_tol, abs_tol=ABS_TOL),
            f"local={local!r}, RiskLabAI={upstream!r}",
        )

    def test_regular_psr_parity(self):
        for sr, count, skew, kurtosis, benchmark in (
            (0.1, 500, 0.0, 3.0, 0.0),
            (0.15, 250, -1.0, 6.0, 0.03),
            (-0.05, 64, 0.4, 4.0, 0.02),
            (0.2, 100, -1.0, 6.0, 0.2),
        ):
            with self.subTest(sr=sr, benchmark=benchmark):
                self.assert_close(
                    self.local.probabilistic_sharpe(sr, count, skew, kurtosis, benchmark),
                    risk_psr(sr, benchmark, count, skew, kurtosis),
                )

    def test_regular_benchmark_and_dsr_parity(self):
        for estimates in (
            [-0.15, -0.02, 0.04, 0.11, 0.23],
            [-0.1, 0.1],
            [0.1, 0.1, 0.1],
        ):
            with self.subTest(estimates=estimates):
                # Both implementations use population cross-trial variance.
                variance = statistics.pvariance(estimates)
                upstream_benchmark = risk_benchmark(estimates)
                self.assert_close(
                    self.local.expected_max_sharpe(len(estimates), variance),
                    upstream_benchmark,
                )

        # Use upstream's DSR function, including its own moment calculation,
        # rather than composing the oracle from benchmark plus PSR here.
        for returns in (
            [-0.03, 0.02, -0.01, 0.04],
            [-0.03, 0.02, 0.01, -0.01, 0.04, 0.005],
        ):
            moments = self.local.moments(returns)
            for trials in (1, 2, 5, 100):
                for variance in (0.0, 0.0025, 1.0):
                    with self.subTest(rows=len(returns), trials=trials, variance=variance):
                        dsr, benchmark = self.local.deflated_sharpe(
                            self.local.sharpe(returns), len(returns),
                            moments["skew"], moments["kurtosis"], trials, variance,
                        )
                        gate = risk_dsr(np.array(returns), trials, math.sqrt(variance))
                        self.assert_close(benchmark, gate["benchmark_sharpe"],
                                          rel_tol=BENCHMARK_REL_TOL)
                        self.assert_close(dsr, gate["deflated_sharpe"],
                                          rel_tol=BENCHMARK_REL_TOL)

    def test_regular_effective_trial_benchmark_parity(self):
        for trials in (1, 2, 5, 100):
            for variance in (0.0, 0.01, 1.0):
                with self.subTest(trials=trials, variance=variance):
                    self.assert_close(
                        self.local.expected_max_sharpe(trials, variance),
                        risk_expected(trials, 0.0, math.sqrt(variance)),
                        rel_tol=BENCHMARK_REL_TOL,
                    )

    def test_regular_sharpe_parity(self):
        returns = [-0.03, 0.02, 0.01, -0.01, 0.04, 0.005]
        self.assert_close(self.local.sharpe(returns), risk_sharpe(np.array(returns)))

    def test_regular_cscv_pbo_parity(self):
        for partitions in (4, 8):
            for metric, callback in (("mean", mean_metric), ("sharpe", None)):
                with self.subTest(partitions=partitions, metric=metric):
                    local = self.local.cscv_pbo(REGULAR_MATRIX, partitions, metric)
                    pbo, logits = risk_pbo(
                        np.array(REGULAR_MATRIX), n_partitions=partitions,
                        metric=callback, n_jobs=1,
                    )
                    self.assertEqual(local["rows_dropped_earliest"], 0)
                    self.assertEqual(len(logits), math.comb(partitions, partitions // 2))
                    # Check every split in order, not just the aggregate PBO.
                    np.testing.assert_allclose(
                        local["logits"], logits, rtol=REL_TOL, atol=ABS_TOL,
                    )
                    self.assert_close(local["pbo"], pbo)
                    self.assertGreater(pbo, 0.0)
                    self.assertLess(pbo, 1.0)

    def test_difference_1_nonpositive_psr_denominator(self):
        # src/.../probabilistic_sharpe_ratio.py:78-86. With SR=1, K=1,
        # skew=1 gives zero variance; skew=2 gives negative variance.
        for skew in (1.0, 2.0):
            with self.subTest(skew=skew):
                self.assertEqual(risk_psr(1.0, 0.0, 20, skew, 1.0), 0.0)
                with self.assertRaisesRegex(ValueError, "non-positive Sharpe variance"):
                    self.local.probabilistic_sharpe(1.0, 20, skew, 1.0)

    def test_difference_2_list_benchmark_single_trial_only(self):
        # The list API returns the estimate, but test_set_overfitting.py:12-56
        # already supports independent N and dispersion, including null N=1.
        self.assertEqual(risk_benchmark([1.5]), 1.5)
        self.assertEqual(risk_expected(1, 0.0, 0.0), 0.0)
        self.assertEqual(self.local.expected_max_sharpe(1, 0.0), 0.0)

    def test_difference_3_unequal_blocks_keep_earliest_rows(self):
        # src/.../probability_of_backtest_overfitting.py:129. Keeping the
        # first outlier reverses the winner in the larger upstream block.
        matrix = [[100.0, -100.0]] + [[-1.0, 1.0]] * 4
        local = self.local.cscv_pbo(matrix, partitions=2)
        pbo, logits = risk_pbo(np.array(matrix), n_partitions=2,
                              metric=mean_metric, n_jobs=1)
        self.assertEqual(local["rows_dropped_earliest"], 1)
        self.assertEqual(local["rows_used"], 4)
        self.assertEqual(local["rows_per_partition"], 2)
        self.assertEqual(local["pbo"], 0.0)
        self.assertEqual(pbo, 1.0)
        np.testing.assert_allclose(logits, [math.log(0.5)] * 2,
                                   rtol=REL_TOL, atol=ABS_TOL)
        # With the same retained rows, the partition discrepancy disappears.
        retained_pbo, retained_logits = risk_pbo(
            np.array(matrix[1:]), n_partitions=2, metric=mean_metric, n_jobs=1,
        )
        self.assertEqual(retained_pbo, local["pbo"])
        np.testing.assert_allclose(retained_logits, local["logits"],
                                   rtol=REL_TOL, atol=ABS_TOL)

    def test_difference_4_ordinal_versus_average_tied_ranks(self):
        # src/.../probability_of_backtest_overfitting.py:69-73. Both select
        # column 0 in sample. Its tied OOS rank is 2 or 3 upstream, depending
        # on NumPy's unspecified tie order, and 2.5 locally.
        matrix = [[1.0, 0.0, 1.0]] * 8
        local = self.local.cscv_pbo(matrix, partitions=4)
        pbo, logits = risk_pbo(np.array(matrix), n_partitions=4,
                              metric=mean_metric, n_jobs=1)
        self.assertEqual(local["in_sample_selection_counts"], [6, 0, 0])
        self.assertEqual(local["pbo"], 0.0)
        np.testing.assert_allclose(local["logits"], [math.log(5 / 3)] * 6,
                                   rtol=REL_TOL, atol=ABS_TOL)
        self.assertEqual(len(logits), 6)
        for logit in logits:
            self.assertTrue(any(math.isclose(logit, math.log(rank / (4 - rank)),
                                            rel_tol=REL_TOL, abs_tol=ABS_TOL)
                                for rank in (2, 3)))
            self.assertFalse(math.isclose(logit, math.log(5 / 3),
                                          rel_tol=REL_TOL, abs_tol=ABS_TOL))
        self.assertEqual(pbo, sum(logit <= 0 for logit in logits) / len(logits))

    def test_difference_5_only_nonstrict_pbo_is_reported_upstream(self):
        # src/.../probability_of_backtest_overfitting.py:77,153-156.
        # No tied metric values: each IS winner is exactly the OOS median.
        matrix = [[3.0, 2.0, 1.0]] * 2 + [[2.0, 3.0, 1.0]] * 2
        local = self.local.cscv_pbo(matrix, partitions=2)
        upstream = risk_pbo(np.array(matrix), n_partitions=2,
                            metric=mean_metric, n_jobs=1)
        self.assertIsInstance(upstream, tuple)
        self.assertEqual(len(upstream), 2)  # PBO and logits; no strict result.
        pbo, logits = upstream
        self.assertEqual(pbo, 1.0)
        np.testing.assert_array_equal(logits, np.zeros(2))
        self.assertEqual(local["lambda_zero_count"], 2)
        self.assertEqual(local["pbo"], 1.0)
        self.assertEqual(local["pbo_strict"], 0.0)

    def test_difference_6_zero_variance_nonzero_mean_sharpe(self):
        # src/.../backtest_statistics.py:50-56. Zero mean is a shared
        # boundary, not a divergence; the local exception requires nonzero mean.
        for value in (-1.0, 1.0):
            returns = [value] * 4
            with self.subTest(value=value):
                self.assertEqual(risk_sharpe(np.array(returns)), 0.0)
                with self.assertRaisesRegex(ValueError, "zero-variance series"):
                    self.local.sharpe(returns)
        self.assertEqual(self.local.sharpe([0.0] * 4), 0.0)
        self.assertEqual(risk_sharpe(np.zeros(4)), 0.0)

        # CSCV's merged-variance policy also treats std <=
        # 1e-12 * max(1, abs(mean)) as zero (overfitting.py:104-112).
        for delta in (0.0, 1e-13):
            with self.subTest(cscv_delta=delta):
                matrix = np.array([[1.0 - delta, -0.2], [1.0 + delta, 0.3]] * 4)
                with self.assertRaisesRegex(ValueError, "zero-variance series"):
                    self.local.cscv_pbo(matrix, partitions=4, metric="sharpe")
                score = risk_sharpe(matrix[:, 0])
                if delta == 0.0:
                    self.assertEqual(score, 0.0)
                else:
                    self.assertTrue(math.isfinite(score))
                    self.assertGreater(score, 1e12)
                pbo, logits = risk_pbo(matrix, n_partitions=4, n_jobs=1)
                self.assertTrue(math.isfinite(pbo))
                self.assertEqual(pbo, 0.0)
                self.assertEqual(len(logits), 6)
                self.assertTrue(np.all(np.isfinite(logits)))


@unittest.skipUnless(UPSTREAM_AVAILABLE, SKIP_REASON)
class ParityRegressionTests(unittest.TestCase):
    def test_native_dsr_oracle_change_is_detected(self):
        case = RiskLabParityTests("test_regular_benchmark_and_dsr_parity")
        case.setUpClass()
        native_gate = risk_dsr

        def changed_gate(*args, **kwargs):
            result = native_gate(*args, **kwargs)
            return {**result, "deflated_sharpe": result["deflated_sharpe"] + 0.01}

        # Change the external oracle at its public API boundary. The parity
        # check must reject it; composing benchmark plus PSR would miss it.
        with patch.dict(case.test_regular_benchmark_and_dsr_parity.__globals__,
                        {"risk_dsr": changed_gate}):
            with self.assertRaises(AssertionError):
                case.test_regular_benchmark_and_dsr_parity()

    def test_tied_rank_check_accepts_either_ordinal_order(self):
        case = RiskLabParityTests("test_difference_4_ordinal_versus_average_tied_ranks")
        case.setUpClass()
        native_argsort = np.argsort

        def alternate_tie_order(values, *args, **kwargs):
            if np.array_equal(values, [1.0, 0.0, 1.0]):
                return np.array([1, 2, 0])
            return native_argsort(values, *args, **kwargs)

        # NumPy does not promise a stable order for equal values. Exercise a
        # valid alternate order while retaining the real upstream PBO function.
        with patch.object(np, "argsort", side_effect=alternate_tie_order):
            case.test_difference_4_ordinal_versus_average_tied_ranks()

    def test_cscv_degenerate_sharpe_oracle_change_is_detected(self):
        case = RiskLabParityTests("test_difference_6_zero_variance_nonzero_mean_sharpe")
        case.setUpClass()

        def invalid_pbo(*args, **kwargs):
            return float("nan"), np.array([float("nan"), float("nan")])

        # A broken upstream CSCV result must fail the policy-6 comparison;
        # checking standalone Sharpe alone would never observe this result.
        with patch.dict(case.test_difference_6_zero_variance_nonzero_mean_sharpe.__globals__,
                        {"risk_pbo": invalid_pbo}):
            with self.assertRaises(AssertionError):
                case.test_difference_6_zero_variance_nonzero_mean_sharpe()


if __name__ == "__main__":
    unittest.main()
