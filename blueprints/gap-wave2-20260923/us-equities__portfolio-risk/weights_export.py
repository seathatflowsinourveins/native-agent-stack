#!/usr/bin/env python3
"""Export skfolio 1.2.9 MeanRisk (default min variance) and HRP fold weights for the Nautilus runners.

Folds are the plan's WalkForward(252, 63, purged 6, reduce_test) on development daily returns, exactly as
cross_val_predict fits them; the reserved fit uses the last 252 development sessions before a 6-session
exclusion. Also exports skfolio's descriptive out-of-sample fold returns (constant weights, daily
rebalanced, cost free) so the reconciled Nautilus P&L can be reported beside them.
"""
import argparse
import importlib.metadata
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
    from skfolio.optimization import HierarchicalRiskParity, MeanRisk

    assert importlib.metadata.version("skfolio") == "1.2.9"
    frozen = common.frozen_panel()
    returns = common.dev_returns(frozen)
    dates = [str(d.date()) for d in returns.index]
    all_dates = frozen["dates"]
    cv = common.walkforward(frozen)
    makers = {"meanrisk_min_variance": MeanRisk, "hrp_variance": HierarchicalRiskParity}
    schedule = []
    for k, (train, test) in enumerate(cv.split(returns)):
        tr, te = returns.iloc[train], returns.iloc[test]
        test_first = dates[test[0]]
        # skfolio applies fold weights from the close of the session before test_first.
        rebalance = all_dates[all_dates.index(test_first) - 1]
        entry = {"id": f"development-{k + 1}", "rebalance_close": rebalance, "test_first": test_first,
                 "test_last": dates[test[-1]], "train_first": dates[train[0]], "train_last": dates[train[-1]],
                 "weights": {}, "descriptive": {}}
        for name, cls in makers.items():
            est = cls().fit(tr)
            w = [float(x) for x in est.weights_]
            entry["weights"][name] = dict(zip(returns.columns, w))
            daily = (te * est.weights_).sum(axis=1).to_numpy()
            entry["descriptive"][name] = {"sessions": len(daily), "sum_daily": float(daily.sum()),
                                          "compounded": float(np.prod(1 + daily) - 1)}
        schedule.append(entry)
    train_r, test_r, _ = common.reserved_frames(frozen)
    # Reserved returns start at 2021-01-05 (vs the 2021-01-04 close), so the rebalance is the 2021-01-04 close.
    test_first = str(test_r.index[0].date())
    reserved = {"id": "reserved-2021q1", "rebalance_close": all_dates[all_dates.index(test_first) - 1],
                "test_first": test_first, "test_last": str(test_r.index[-1].date()),
                "train_first": str(train_r.index[0].date()), "train_last": str(train_r.index[-1].date()),
                "weights": {}, "descriptive": {}}
    for name, cls in makers.items():
        est = cls().fit(train_r)
        reserved["weights"][name] = dict(zip(train_r.columns, [float(x) for x in est.weights_]))
        daily = (test_r * est.weights_).sum(axis=1).to_numpy()
        reserved["descriptive"][name] = {"sessions": len(daily), "sum_daily": float(daily.sum()),
                                         "compounded": float(np.prod(1 + daily) - 1)}
    schedule.append(reserved)
    out = {"skfolio": "1.2.9", "plan_sha256": frozen["plan_sha256"], "assets": frozen["plan"]["assets"],
           "final_close": all_dates[-1], "schedule": schedule, "inputs_unchanged": common.inputs_unchanged(frozen)}
    assert out["inputs_unchanged"]
    common.dump(args.out, out)
    print(common.digest(args.out))


if __name__ == "__main__":
    main()
