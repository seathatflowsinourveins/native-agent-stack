"""Backtest-overfitting controls written from the primary papers (standard library only).

Sources (formulas transcribed from the papers; no third-party code was copied):

* Probabilistic Sharpe ratio (PSR): D. H. Bailey and M. Lopez de Prado,
  "The Sharpe Ratio Efficient Frontier", Journal of Risk 15(2), 2012, 3-44.
  PSR(SR*) = Phi((SR - SR*) * sqrt(T - 1) / sqrt(1 - g3 * SR + (g4 - 1) / 4 * SR^2)),
  with g3 the skewness and g4 the (non-excess) kurtosis of the returns.
* Deflated Sharpe ratio (DSR): D. H. Bailey and M. Lopez de Prado, "The Deflated
  Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and
  Non-Normality", Journal of Portfolio Management 40(5), 2014, 94-107
  (SSRN 2460551). DSR = PSR(SR0) with
  SR0 = sqrt(V[SR_n]) * ((1 - gamma) * Phi^-1(1 - 1/N) + gamma * Phi^-1(1 - 1/(N e))),
  gamma the Euler-Mascheroni constant, N the number of independent trials.
* Probability of backtest overfitting (PBO) by combinatorially symmetric
  cross-validation (CSCV): D. H. Bailey, J. M. Borwein, M. Lopez de Prado and
  Q. J. Zhu, "The Probability of Backtest Overfitting", Journal of
  Computational Finance 20(4), 2017, 39-69 (SSRN 2326253).

Sharpe ratios here are per-observation (not annualized) unless a caller scales them.
"""
from __future__ import annotations

from itertools import combinations
import math
from statistics import NormalDist

EULER_GAMMA = 0.5772156649015329
_NORMAL = NormalDist()


def moments(values):
    """Population mean, standard deviation, skewness and non-excess kurtosis."""
    xs = [float(x) for x in values]
    n = len(xs)
    if n < 2 or not all(math.isfinite(x) for x in xs):
        raise ValueError("need at least two finite observations")
    mean = math.fsum(xs) / n
    dev = [x - mean for x in xs]
    m2 = math.fsum(d * d for d in dev) / n
    if m2 == 0.0:
        return {"n": n, "mean": mean, "std": 0.0, "skew": None, "kurtosis": None}
    m3 = math.fsum(d ** 3 for d in dev) / n
    m4 = math.fsum(d ** 4 for d in dev) / n
    return {"n": n, "mean": mean, "std": math.sqrt(m2), "skew": m3 / m2 ** 1.5, "kurtosis": m4 / m2 ** 2}


def sharpe_from(mean, std):
    if std > 0.0:
        return mean / std
    if mean == 0.0:
        return 0.0
    raise ValueError("zero-variance series with nonzero mean has no finite Sharpe ratio")


def sharpe(values):
    stats = moments(values)
    return sharpe_from(stats["mean"], stats["std"])


def probabilistic_sharpe(sr, t, skew, kurtosis, sr_benchmark=0.0):
    """PSR: probability that the true Sharpe exceeds sr_benchmark (Bailey and Lopez de Prado 2012)."""
    if t < 2:
        raise ValueError("need at least two observations")
    variance_term = 1.0 - skew * sr + (kurtosis - 1.0) / 4.0 * sr * sr
    if not variance_term > 0.0:
        raise ValueError("non-positive Sharpe variance term")
    z = (sr - sr_benchmark) * math.sqrt(t - 1) / math.sqrt(variance_term)
    return _NORMAL.cdf(z)


def expected_max_sharpe(trials, variance):
    """Expected maximum Sharpe of `trials` independent null trials (Bailey and Lopez de Prado 2014)."""
    if not isinstance(trials, int) or trials < 1:
        raise ValueError("trials must be a positive integer")
    if not variance >= 0.0:
        raise ValueError("variance must be nonnegative")
    if trials == 1:
        return 0.0  # no selection among trials: the null benchmark is zero
    return math.sqrt(variance) * ((1.0 - EULER_GAMMA) * _NORMAL.inv_cdf(1.0 - 1.0 / trials)
                                  + EULER_GAMMA * _NORMAL.inv_cdf(1.0 - 1.0 / (trials * math.e)))


def deflated_sharpe(sr, t, skew, kurtosis, trials, trial_variance):
    """DSR = PSR evaluated at the expected maximum null Sharpe; returns (dsr, sr0)."""
    sr0 = expected_max_sharpe(trials, trial_variance)
    return probabilistic_sharpe(sr, t, skew, kurtosis, sr0), sr0


def _merge(a, b):
    """Chan et al. parallel combination of (count, mean, M2) aggregates."""
    n = a[0] + b[0]
    delta = b[1] - a[1]
    mean = a[1] + delta * b[0] / n
    return (n, mean, a[2] + b[2] + delta * delta * a[0] * b[0] / n)


def _aggregate(rows):
    n = len(rows)
    mean = math.fsum(rows) / n
    return (n, mean, math.fsum((x - mean) ** 2 for x in rows))


def _score(aggregate, metric):
    n, mean, m2 = aggregate
    if metric == "mean":
        return mean
    if metric == "sharpe":
        std = math.sqrt(max(m2, 0.0) / n)
        if std <= 1e-12 * max(1.0, abs(mean)):
            std = 0.0  # merged M2 of a constant column can carry rounding residue
        return sharpe_from(mean, std)
    raise ValueError("metric must be 'mean' or 'sharpe'")


def _average_ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return ranks


def cscv_pbo(matrix, partitions=16, metric="mean"):
    """Probability of backtest overfitting by CSCV.

    matrix: T rows (chronological observations) by N columns (trials).
    The earliest T mod S rows are dropped so the S contiguous blocks are equal.
    For every choice of S/2 blocks as the in-sample set J (complement J-bar out of
    sample): n* = argmax in-sample metric (ties by column order), omega = average
    ascending out-of-sample rank of n* / (N + 1), lambda = logit(omega).
    PBO is the share of combinations with lambda <= 0.

    degradation_slope is the paper's pooled OLS slope of the selected trial's
    out-of-sample metric on its in-sample metric. It is not evidence of ranking
    persistence here. With metric="mean" and equal complementary halves, every
    trial satisfies in_sample + out_of_sample = 2 * (its mean over the used rows),
    so all splits that select the same trial lie on a line of slope exactly -1.
    The pooled slope is therefore mostly this identity, mixed with the spread
    between the full-sample means of the trials that get selected. With
    metric="sharpe" the identity is not exact, but the complementary halves still
    induce the same negative within-trial dependence. Judge persistence by PBO
    against its no-skill level (about 0.5 for continuous ranks), not by the slope.
    """
    rows = [[float(x) for x in row] for row in matrix]
    if not rows or any(len(r) != len(rows[0]) for r in rows):
        raise ValueError("matrix must be rectangular and nonempty")
    t, n = len(rows), len(rows[0])
    if n < 2:
        raise ValueError("need at least two trials")
    if not isinstance(partitions, int) or partitions < 2 or partitions % 2:
        raise ValueError("partitions must be an even integer >= 2")
    size = t // partitions
    if size < 2:
        raise ValueError("each partition needs at least two rows")
    if not all(math.isfinite(x) for r in rows for x in r):
        raise ValueError("nonfinite performance value")
    dropped = t - size * partitions
    used = rows[dropped:]
    blocks = [[_aggregate([used[b * size + i][c] for i in range(size)]) for c in range(n)]
              for b in range(partitions)]

    def combine(indices, column):
        agg = blocks[indices[0]][column]
        for b in indices[1:]:
            agg = _merge(agg, blocks[b][column])
        return agg

    logits, selected_is, selected_oos, chosen_counts = [], [], [], [0] * n
    for chosen_blocks in combinations(range(partitions), partitions // 2):
        rest = tuple(b for b in range(partitions) if b not in chosen_blocks)
        in_sample = [_score(combine(chosen_blocks, c), metric) for c in range(n)]
        out_sample = [_score(combine(rest, c), metric) for c in range(n)]
        best = max(range(n), key=lambda c: (in_sample[c], -c))
        omega = _average_ranks(out_sample)[best] / (n + 1)
        logits.append(math.log(omega / (1.0 - omega)))
        selected_is.append(in_sample[best])
        selected_oos.append(out_sample[best])
        chosen_counts[best] += 1
    count = len(logits)
    at_or_below = sum(x <= 0.0 for x in logits)
    zero = sum(x == 0.0 for x in logits)
    mean_is = math.fsum(selected_is) / count
    mean_oos = math.fsum(selected_oos) / count
    sxx = math.fsum((x - mean_is) ** 2 for x in selected_is)
    slope = (math.fsum((x - mean_is) * (y - mean_oos) for x, y in zip(selected_is, selected_oos)) / sxx
             if sxx > 0 else None)
    return {
        "partitions": partitions, "metric": metric, "rows": t, "rows_used": len(used),
        "rows_dropped_earliest": dropped, "rows_per_partition": size, "trials": n,
        "combinations": count, "pbo": at_or_below / count, "pbo_strict": (at_or_below - zero) / count,
        "lambda_zero_count": zero, "lambda_mean": math.fsum(logits) / count,
        "lambda_min": min(logits), "lambda_max": max(logits),
        "probability_oos_loss": sum(y < 0.0 for y in selected_oos) / count,
        "selected_in_sample_mean": mean_is, "selected_out_of_sample_mean": mean_oos,
        "degradation_slope": slope,
        "degradation_intercept": (mean_oos - slope * mean_is) if slope is not None else None,
        "in_sample_selection_counts": chosen_counts, "logits": logits,
    }
