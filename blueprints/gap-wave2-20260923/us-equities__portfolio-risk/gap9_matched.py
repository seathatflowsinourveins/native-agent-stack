#!/usr/bin/env python3
"""Gap 9: one matched run of skfolio, cvxportfolio, empyrical-reloaded and quantstats.

Common inputs: frozen plan.json development daily close-to-close raw returns (2015-01-05..2020-12-31).
Common temporal boundaries: skfolio WalkForward(252, 63, purged 6, reduce_test) folds from plan.json.
Common cost: the plan's 20bp round-trip proxy, charged once per fold on the fold's first test day,
proportional to invested weight (identical to evaluate.py's fully-invested convention).
Optimizers (skfolio MeanRisk minimum variance, cvxportfolio SinglePeriodOptimization minimum variance)
see only their fold's training rows. Metrics libraries (skfolio.measures, empyrical-reloaded, quantstats)
score every resulting net series with 252 periods per year and zero risk-free rate. No winner is declared.
"""
import argparse
import importlib.metadata
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

PINS = {"skfolio": "1.2.9", "cvxportfolio": "1.5.1", "empyrical-reloaded": "0.5.12", "quantstats": "0.0.81"}
COST = 0.002
PERIODS = 252


def cvx_weights(train, workdir):
    import cvxportfolio as cvx
    import pandas as pd
    # Convert backward-aligned rows (return realized at date d) to cvxportfolio's forward alignment:
    # each training return is indexed at the preceding row's date (the first at a label one day earlier),
    # and the policy executes at the last training date, so exactly the training rows are "past".
    dates = list(train.index)
    fwd = train.copy()
    fwd.index = pd.DatetimeIndex([dates[0] - pd.Timedelta(days=1)] + dates[:-1])
    t = dates[-1]
    exec_row = pd.DataFrame([[0.0] * train.shape[1]], columns=train.columns, index=pd.DatetimeIndex([t]))
    fwd = pd.concat([fwd, exec_row])
    fwd["USDOLLAR"] = 0.0
    md = cvx.UserProvidedMarketData(returns=fwd, min_history=pd.Timedelta(0), base_location=workdir, cash_key="USDOLLAR")
    policy = cvx.SinglePeriodOptimization(
        objective=-cvx.FullCovariance(cvx.forecast.HistoricalFactorizedCovariance(kelly=False)),
        constraints=[cvx.LongOnly(), cvx.NoCash()])
    h = pd.Series({a: 0.0 for a in train.columns} | {"USDOLLAR": 1_000_000.0})
    u, t_exec, _ = policy.execute(h=h, market_data=md, t=t)
    post = (h + u)
    w = (post / post.sum()).drop("USDOLLAR").clip(lower=0.0)
    return (w / w.sum()).reindex(train.columns), len(fwd) - 1, str(t_exec)


def metrics(series):
    import empyrical as ep
    import numpy as np
    import quantstats as qs
    import skfolio.measures as sm
    r = series.to_numpy()
    mu, sd, semi = sm.mean(r), sm.standard_deviation(r), sm.semi_deviation(r, min_acceptable_return=0.0)
    out = {
        "skfolio.measures": {"annualized_return": mu * PERIODS, "annualized_volatility": sd * math.sqrt(PERIODS),
                             "sharpe": mu / sd * math.sqrt(PERIODS), "sortino": mu / semi * math.sqrt(PERIODS),
                             "max_drawdown": -sm.max_drawdown(sm.get_drawdowns(r, compounded=True))},
        "empyrical-reloaded": {"annualized_return": ep.annual_return(series, period="daily"),
                               "annualized_volatility": ep.annual_volatility(series, period="daily"),
                               "sharpe": ep.sharpe_ratio(series, risk_free=0, period="daily"),
                               "sortino": ep.sortino_ratio(series, required_return=0, period="daily"),
                               "max_drawdown": ep.max_drawdown(series)},
        "quantstats": {"annualized_return": qs.stats.cagr(series, rf=0.0, compounded=True, periods=PERIODS),
                       "annualized_volatility": qs.stats.volatility(series, periods=PERIODS, annualize=True),
                       "sharpe": qs.stats.sharpe(series, rf=0.0, periods=PERIODS, annualize=True),
                       "sortino": qs.stats.sortino(series, rf=0, periods=PERIODS, annualize=True),
                       "max_drawdown": qs.stats.max_drawdown(series)},
    }
    for lib, values in out.items():
        for key, value in values.items():
            values[key] = float(value)
            if not math.isfinite(values[key]):
                raise ValueError(f"non-finite {lib}.{key}")
    out["conventions"] = {
        "skfolio.measures": "arithmetic mean x 252; semi_deviation below 0; compounded max drawdown",
        "empyrical-reloaded": "geometric annual_return (CAGR); downside deviation below 0",
        "quantstats": "CAGR over calendar years of the index; sortino downside over all periods"}
    out["observations"] = int(len(r))
    out["total_compounded_return"] = float(np.prod(1 + r) - 1)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workdir", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit("use a fresh output path")
    versions = {p: importlib.metadata.version(p) for p in PINS}
    if versions != PINS:
        raise SystemExit(f"versions {versions} differ from pins {PINS}")
    import pandas as pd
    from skfolio.optimization import MeanRisk

    frozen = common.frozen_panel()
    returns = common.dev_returns(frozen)
    cv = common.walkforward(frozen)
    purged = frozen["plan"]["splitter"]["purged_size"]
    series = {"skfolio_meanrisk_min_variance": [], "cvxportfolio_spo_min_variance": [], "equal_weight_control": []}
    folds = []
    for k, (train, test) in enumerate(cv.split(returns)):
        if not (train[-1] + purged < test[0]):
            raise ValueError("fold boundary violates the purge gap")
        tr, te = returns.iloc[train], returns.iloc[test]
        sk = MeanRisk().fit(tr)
        w_sk = pd.Series(sk.weights_, index=returns.columns)
        w_cvx, cvx_rows, t_exec = cvx_weights(tr, args.workdir / f"fold-{k + 1}")
        w_eq = pd.Series(1.0 / returns.shape[1], index=returns.columns)
        fold = {"fold": k + 1, "train_first": str(tr.index[0].date()), "train_last": str(tr.index[-1].date()),
                "test_first": str(te.index[0].date()), "test_last": str(te.index[-1].date()),
                "train_rows": len(train), "test_rows": len(test), "cvxportfolio_history_rows": cvx_rows,
                "cvxportfolio_execute_time": t_exec, "weights": {}}
        if cvx_rows != len(train):
            raise ValueError("cvxportfolio saw a different history length than the training fold")
        for name, w in [("skfolio_meanrisk_min_variance", w_sk), ("cvxportfolio_spo_min_variance", w_cvx),
                        ("equal_weight_control", w_eq)]:
            gross = te @ w
            net = gross.copy()
            net.iloc[0] -= COST * float(w.sum())
            series[name].append(net)
            fold["weights"][name] = {a: float(x) for a, x in w.items()}
        folds.append(fold)
    report = {"versions": versions, "python": sys.version.split()[0], "plan_sha256": frozen["plan_sha256"],
              "cost_proxy": {"round_trip_fraction": COST, "charged": "once per fold on the first test day x invested weight"},
              "periods_per_year": PERIODS, "risk_free": 0.0, "folds": folds, "series": {}}
    for name, parts in series.items():
        s = pd.concat(parts)
        if s.index.duplicated().any():
            raise ValueError("overlapping test folds")
        report["series"][name] = metrics(s)
    max_gap = max(abs(folds[i]["weights"]["skfolio_meanrisk_min_variance"][a] - folds[i]["weights"]["cvxportfolio_spo_min_variance"][a])
                  for i in range(len(folds)) for a in returns.columns)
    report["max_abs_weight_difference_skfolio_vs_cvxportfolio"] = max_gap
    report["inputs_unchanged"] = common.inputs_unchanged(frozen)
    if not report["inputs_unchanged"]:
        raise ValueError("inputs changed")
    common.dump(args.out, report)
    print(common.digest(args.out))


if __name__ == "__main__":
    main()
