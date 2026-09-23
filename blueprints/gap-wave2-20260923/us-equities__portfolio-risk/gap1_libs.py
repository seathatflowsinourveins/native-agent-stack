#!/usr/bin/env python3
"""Gap 1: execute cvxportfolio, empyrical-reloaded or quantstats (one per process) on frozen plan.json returns.

Run in the hashed candidate-libs venv with a temporary HOME so library caches stay out of the real home.
"""
import argparse
import importlib.metadata
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

PINS = {"cvxportfolio": "1.5.1", "empyrical-reloaded": "0.5.12", "quantstats": "0.0.81", "skfolio": "1.2.9"}


def finite(values):
    for key, value in values.items():
        if not math.isfinite(float(value)):
            raise ValueError(f"non-finite {key}: {value}")
    return {k: float(v) for k, v in values.items()}


def equal_weight_dev(frozen):
    returns = common.dev_returns(frozen)
    return returns.mean(axis=1)


def run_cvxportfolio(frozen, workdir):
    import cvxportfolio as cvx
    import pandas as pd
    closes = common.price_frame(frozen, frozen["eligible"] + frozen["reserved"])
    # cvxportfolio returns are forward-aligned: the row at t is the return realized from t to the next period.
    fwd = (closes.shift(-1) / closes - 1).iloc[:-1]
    fwd["USDOLLAR"] = 0.0
    md = cvx.UserProvidedMarketData(returns=fwd, min_history=pd.Timedelta(0), base_location=workdir,
                                    cash_key="USDOLLAR")
    policy = cvx.SinglePeriodOptimization(
        objective=-cvx.FullCovariance(cvx.forecast.HistoricalFactorizedCovariance(kelly=False)),
        constraints=[cvx.LongOnly(), cvx.NoCash()])
    t = pd.Timestamp(frozen["dates"][frozen["reserved"][0]])
    h = pd.Series({a: 0.0 for a in frozen["plan"]["assets"]} | {"USDOLLAR": 1_000_000.0})
    u, t_exec, _ = policy.execute(h=h, market_data=md, t=t)
    post = h + u
    weights = (post / post.sum()).drop("USDOLLAR")
    sim = cvx.MarketSimulator(market_data=md, base_location=workdir)
    result = sim.backtest(policy, start_time=t, end_time=fwd.index[-1], initial_value=1_000_000.0)
    out = {"execute_time": str(t_exec), "execute_weights": finite(weights.to_dict()),
           "execute_cash_weight": float(post["USDOLLAR"] / post.sum()),
           "backtest_start": str(t.date()), "backtest_end": str(fwd.index[-1].date()),
           "backtest_periods": int(len(result.v)),
           "backtest_final_value": float(result.v.iloc[-1]),
           "backtest_sharpe_ratio": float(result.sharpe_ratio),
           "backtest_period_volatility": float(result.volatility),
           "backtest_annualized_volatility": float(result.annualized_volatility),
           "backtest_annualized_return": float(result.annualized_average_return)}
    finite({k: v for k, v in out.items() if isinstance(v, float)})
    return out


def run_empyrical(frozen, _workdir):
    import empyrical as ep
    r = equal_weight_dev(frozen)
    return {"series": "equal-weight SPY/QQQ/IWM daily close-to-close raw returns 2015-01-05..2020-12-31",
            "observations": int(len(r)), **finite({
                "annual_return": ep.annual_return(r, period="daily"),
                "annual_volatility": ep.annual_volatility(r, period="daily"),
                "sharpe_ratio": ep.sharpe_ratio(r, risk_free=0, period="daily"),
                "sortino_ratio": ep.sortino_ratio(r, required_return=0, period="daily"),
                "max_drawdown": ep.max_drawdown(r)})}


def run_quantstats(frozen, _workdir):
    import quantstats as qs
    r = equal_weight_dev(frozen)
    return {"series": "equal-weight SPY/QQQ/IWM daily close-to-close raw returns 2015-01-05..2020-12-31",
            "observations": int(len(r)), **finite({
                "cagr": qs.stats.cagr(r, rf=0.0, compounded=True, periods=252),
                "volatility": qs.stats.volatility(r, periods=252, annualize=True),
                "sharpe": qs.stats.sharpe(r, rf=0.0, periods=252, annualize=True),
                "sortino": qs.stats.sortino(r, rf=0, periods=252, annualize=True),
                "max_drawdown": qs.stats.max_drawdown(r)})}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lib", choices=["cvxportfolio", "empyrical-reloaded", "quantstats"], required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workdir", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit("use a fresh output path")
    version = importlib.metadata.version(args.lib)
    if version != PINS[args.lib]:
        raise SystemExit(f"{args.lib} {version} is not the pinned {PINS[args.lib]}")
    frozen = common.frozen_panel()
    runner = {"cvxportfolio": run_cvxportfolio, "empyrical-reloaded": run_empyrical, "quantstats": run_quantstats}[args.lib]
    body = runner(frozen, args.workdir)
    result = {"library": args.lib, "version": version, "python": sys.version.split()[0],
              "plan_sha256": frozen["plan_sha256"], "result": body, "inputs_unchanged": common.inputs_unchanged(frozen)}
    if not result["inputs_unchanged"]:
        raise SystemExit("inputs changed")
    common.dump(args.out, result)
    print(common.digest(args.out))


if __name__ == "__main__":
    main()
