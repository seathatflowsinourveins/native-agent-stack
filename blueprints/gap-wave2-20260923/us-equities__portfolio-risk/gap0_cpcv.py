#!/usr/bin/env python3
"""Gap 0: skfolio CombinatorialPurgedCV with explicit prior/covariance estimators in MeanRisk.

Runs in the requirements.lock venv (skfolio 1.2.9, Python 3.13.15) on the frozen plan.json inputs.
"""
import argparse
import importlib.metadata
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit("use a fresh output path")
    import numpy as np
    from skfolio.model_selection import CombinatorialPurgedCV, cross_val_predict
    from skfolio.moments import LedoitWolf, ShrunkCovariance
    from skfolio.optimization import MeanRisk
    from skfolio.prior import EmpiricalPrior

    assert importlib.metadata.version("skfolio") == "1.2.9"
    frozen = common.frozen_panel()
    returns = common.dev_returns(frozen)
    cv = CombinatorialPurgedCV(n_folds=10, n_test_folds=2, purged_size=6, embargo_size=0)
    assert cv.n_splits == 45 and cv.n_test_paths == 9, (cv.n_splits, cv.n_test_paths)
    arms = {
        "meanrisk_empiricalprior_ledoitwolf": (LedoitWolf, lambda: MeanRisk(prior_estimator=EmpiricalPrior(covariance_estimator=LedoitWolf()))),
        "meanrisk_empiricalprior_shrunkcovariance": (ShrunkCovariance, lambda: MeanRisk(prior_estimator=EmpiricalPrior(covariance_estimator=ShrunkCovariance()))),
    }
    result = {"skfolio": importlib.metadata.version("skfolio"), "numpy": np.__version__,
              "plan_sha256": frozen["plan_sha256"], "evaluate_sha256": frozen["evaluate_sha256"],
              "cv": {"class": "CombinatorialPurgedCV", "n_folds": 10, "n_test_folds": 2, "purged_size": 6,
                     "embargo_size": 0, "n_splits": cv.n_splits, "n_test_paths": cv.n_test_paths},
              "development_observations": len(returns), "development_first": str(returns.index[0].date()),
              "development_last": str(returns.index[-1].date()), "arms": {}}
    train_r, test_r, _ = common.reserved_frames(frozen)
    for name, (cov_cls, make) in arms.items():
        population = cross_val_predict(make(), returns, cv=cv)
        paths = list(population)
        assert len(paths) == 9, len(paths)
        sharpe = [float(p.annualized_sharpe_ratio) for p in paths]
        ann_ret = [float(p.annualized_mean) for p in paths]
        ann_vol = [float(p.annualized_standard_deviation) for p in paths]
        assert all(math.isfinite(x) for x in sharpe + ann_ret + ann_vol)
        fitted = make().fit(train_r)
        cov_fitted = fitted.prior_estimator_.covariance_estimator_
        assert isinstance(cov_fitted, cov_cls), type(cov_fitted)
        w = [float(x) for x in fitted.weights_]
        assert all(math.isfinite(x) and x >= -1e-9 for x in w) and abs(sum(w) - 1) < 1e-6, w
        test_port = (test_r * fitted.weights_).sum(axis=1).to_numpy()
        result["arms"][name] = {
            "cpcv_paths": len(paths),
            "cpcv_path_observations": [len(p.returns) for p in paths],
            "cpcv_path_annualized_sharpe": sharpe,
            "cpcv_path_annualized_mean": ann_ret,
            "cpcv_path_annualized_std": ann_vol,
            "cpcv_sharpe_mean": float(np.mean(sharpe)), "cpcv_sharpe_std": float(np.std(sharpe, ddof=1)),
            "fitted_covariance_estimator": type(cov_fitted).__name__,
            "fitted_shrinkage": float(getattr(cov_fitted, "shrinkage_", getattr(cov_fitted, "shrinkage", float("nan")))),
            "reserved_fit_first": str(train_r.index[0].date()), "reserved_fit_last": str(train_r.index[-1].date()),
            "reserved_weights": dict(zip(frozen["plan"]["assets"], w)),
            "reserved_2021q1_daily_observations": len(test_port),
            "reserved_2021q1_mean_daily_return": float(np.mean(test_port)),
            "reserved_2021q1_std_daily_return": float(np.std(test_port, ddof=1)),
        }
    result["inputs_unchanged"] = common.inputs_unchanged(frozen)
    assert result["inputs_unchanged"]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    common.dump(args.out, result)
    print(common.digest(args.out))


if __name__ == "__main__":
    main()
