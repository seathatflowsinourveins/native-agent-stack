"""Stdlib percentile bootstrap and Holm adjustment with cited algorithms.

Paired indices/percentiles: SciPy v1.18.1@e4e854eaa8f18d807cd3496028e257e36caa93cc,
scipy/stats/_resampling.py L363-L367, L549-L560, L650-L663. This implements the
percentile method explicitly; SciPy's default BCa method is not used.
Holm step-down: statsmodels v0.15.0@278ff9950636cdd4939b4055e339a8e681d79cab,
statsmodels/stats/multitest.py L233-L244. No p-values are inferred from a CI.
"""

import math
import random
from collections.abc import Mapping, Sequence
from typing import Any


def _percentile(ordered: list[float], fraction: float) -> float:
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _bootstrap(values: list[float], resamples: int, seed: int) -> dict[str, Any]:
    if resamples < 1:
        raise ValueError("resamples must be positive")
    if not values:
        return {"n": 0, "estimate": None, "ci95": None, "resamples": resamples, "seed": seed}
    if any(not math.isfinite(value) for value in values):
        raise ValueError("Scores must be finite")
    rng = random.Random(seed)
    n = len(values)
    distribution = sorted(
        sum(rng.choices(values, k=n)) / n for _ in range(resamples)
    )
    return {
        "n": n, "estimate": sum(values) / n,
        "ci95": [_percentile(distribution, 0.025), _percentile(distribution, 0.975)],
        "resamples": resamples, "seed": seed,
    }


def accuracy(labels: Sequence[bool | int], resamples: int = 10_000, seed: int = 20261002) -> dict[str, Any]:
    if any(label not in (False, True) for label in labels):
        raise ValueError("Accuracy labels must be zero or one")
    result = _bootstrap([float(label) for label in labels], resamples, seed)
    result["accuracy"] = result.pop("estimate")
    return result


def _labels(records: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    labels = {}
    for record in records:
        qid = record["question_id"]
        if qid in labels:
            raise ValueError(f"Duplicate question id: {qid}")
        label = record["autoeval_label"]["label"]
        if label not in (False, True):
            raise ValueError("Paired accuracy labels must be zero or one")
        labels[qid] = float(label)
    return labels


def paired_difference(
    arm_a: Sequence[Mapping[str, Any]], arm_b: Sequence[Mapping[str, Any]],
    resamples: int = 10_000, seed: int = 20261002,
) -> dict[str, Any]:
    """A minus B, aligning questions before resampling paired differences.

    Reject unmatched questions; silently taking different arm samples would
    change the estimand. Callers may explicitly preselect a shared subset.
    """
    labels_a, labels_b = _labels(arm_a), _labels(arm_b)
    if labels_a.keys() != labels_b.keys():
        raise ValueError("Paired arms must contain exactly the same question ids")
    qids = sorted(labels_a)
    result = _bootstrap([labels_a[qid] - labels_b[qid] for qid in qids], resamples, seed)
    result["difference"] = result.pop("estimate")
    result["question_ids"] = qids
    return result


def holm_adjust(p_values: Sequence[float]) -> list[float]:
    """Adjusted p-values in original order; callers supply valid test p-values."""
    if any(not math.isfinite(value) or value < 0 or value > 1 for value in p_values):
        raise ValueError("p-values must be finite and between zero and one")
    order = sorted(range(len(p_values)), key=lambda index: p_values[index])
    adjusted = [0.0] * len(p_values)
    previous = 0.0
    for rank, index in enumerate(order):
        previous = max(previous, (len(p_values) - rank) * p_values[index])
        adjusted[index] = min(previous, 1.0)
    return adjusted
