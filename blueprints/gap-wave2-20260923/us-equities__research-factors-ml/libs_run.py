#!/usr/bin/env python3
"""Single-library executions on the frozen SPY/QQQ/IWM plan.json data (gap 5 arms).

--arm statsmodels | arch | statsforecast | alphalens | sktime | tsfresh | river | arcticdb
Each arm prints one JSON object; the caller records exit code and output sha256.
"""
import argparse
import datetime as dt
from decimal import Decimal
import importlib.metadata
import json
from pathlib import Path
import sys
import warnings

REPO = Path(__file__).resolve().parents[3]
EVAL_DIR = REPO / "blueprints/us-equities/research-evaluation"
sys.path.insert(0, str(EVAL_DIR))
import evaluate as ev  # noqa: E402


def frame(root):
    import pandas as pd
    plan = json.loads((EVAL_DIR / "plan.json").read_text())
    ev.verify_inputs(root, plan["inputs"])
    panel, dates, _a, _c = ev.load_panel(root, plan)
    close = pd.DataFrame({a: [float(r["close"]) for r in panel[a]] for a in plan["assets"]}, index=pd.to_datetime(dates))
    return plan, close


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--arm", required=True)
    p.add_argument("--lean-source", type=Path, required=True)
    p.add_argument("--tmp", type=Path)
    a = p.parse_args()
    import numpy as np
    import pandas as pd
    plan, close = frame(a.lean_source.resolve())
    dev = close.loc[:plan["development_end"]]
    out = {"arm": a.arm, "plan_sha256": ev.digest(EVAL_DIR / "plan.json")}
    if a.arm == "statsmodels":
        from statsmodels.tsa.arima.model import ARIMA
        from statsmodels.stats.diagnostic import acorr_ljungbox
        y = np.log(dev["SPY"].to_numpy()[-252:])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = ARIMA(y, order=(1, 1, 1), trend="n").fit()
        lb = acorr_ljungbox(res.resid[1:], lags=[5, 10], return_df=True)
        out.update(version=importlib.metadata.version("statsmodels"), params={k: round(float(v), 6) for k, v in zip(res.param_names, res.params)},
                   aic=round(float(res.aic), 4), forecast_log_close_5=[round(float(v), 6) for v in res.forecast(5)],
                   last_log_close=round(float(y[-1]), 6), ljung_box_resid_pvalue={"lag5": round(float(lb["lb_pvalue"].iloc[0]), 4), "lag10": round(float(lb["lb_pvalue"].iloc[1]), 4)})
    elif a.arm == "statsmodels_lb_df2":
        # Fix round 3: same fit as the statsmodels arm; Ljung-Box with model_df=2 (AR1 + MA1).
        from statsmodels.tsa.arima.model import ARIMA
        from statsmodels.stats.diagnostic import acorr_ljungbox
        y = np.log(dev["SPY"].to_numpy()[-252:])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = ARIMA(y, order=(1, 1, 1), trend="n").fit()
        lb0 = acorr_ljungbox(res.resid[1:], lags=[5, 10], return_df=True)
        lb2 = acorr_ljungbox(res.resid[1:], lags=[5, 10], model_df=2, return_df=True)
        out.update(version=importlib.metadata.version("statsmodels"),
                   ljung_box_model_df0_pvalue={"lag5": round(float(lb0["lb_pvalue"].iloc[0]), 6), "lag10": round(float(lb0["lb_pvalue"].iloc[1]), 6)},
                   ljung_box_model_df2_pvalue={"lag5": round(float(lb2["lb_pvalue"].iloc[0]), 6), "lag10": round(float(lb2["lb_pvalue"].iloc[1]), 6)})
    elif a.arm == "arch":
        from arch import arch_model
        r = 100 * np.log(dev["SPY"]).diff().loc[plan["eligible_start"]:].dropna()
        res = arch_model(r, mean="Constant", vol="GARCH", p=1, q=1, dist="normal").fit(disp="off")
        f = res.forecast(horizon=5, reindex=False)
        out.update(version=importlib.metadata.version("arch"), n=int(len(r)), params={k: round(float(v), 6) for k, v in res.params.items()},
                   loglik=round(float(res.loglikelihood), 4), variance_forecast_pct2=[round(float(v), 6) for v in f.variance.iloc[-1]],
                   convergence_flag=int(res.convergence_flag))
    elif a.arm == "statsforecast":
        from statsforecast import StatsForecast
        from statsforecast.models import AutoARIMA
        tail = np.log(dev.iloc[-252:])
        long = pd.DataFrame({"unique_id": np.repeat(tail.columns, len(tail)), "ds": np.tile(np.arange(len(tail)), len(tail.columns)),
                             "y": np.concatenate([tail[c].to_numpy() for c in tail.columns])})
        fc = StatsForecast(models=[AutoARIMA(season_length=1)], freq=1, n_jobs=1).forecast(df=long, h=5)
        out.update(version=importlib.metadata.version("statsforecast"),
                   forecast_log_close={u: [round(float(v), 6) for v in g["AutoARIMA"]] for u, g in fc.groupby("unique_id")},
                   last_log_close={c: round(float(tail[c].iloc[-1]), 6) for c in tail.columns})
    elif a.arm == "alphalens":
        import alphalens as al
        factors = {}
        for L in (20, 60, 120):
            s = (dev / dev.shift(L) - 1).loc[plan["eligible_start"]:].stack()
            s.index.names = ["date", "asset"]
            factors["momentum" + str(L)] = s
        ics = {}
        for name, f in factors.items():
            clean = al.utils.get_clean_factor_and_forward_returns(f, dev, quantiles=None, bins=3, periods=(1, 5), max_loss=0.35)
            ic = al.performance.factor_information_coefficient(clean)
            ics[name] = {"rows": int(len(clean)), "mean_ic": {c: round(float(v), 6) for c, v in ic.mean().items()},
                         "ic_std": {c: round(float(v), 6) for c, v in ic.std().items()}, "sessions": int(len(ic))}
        out.update(version=importlib.metadata.version("alphalens-reloaded"), pandas=importlib.metadata.version("pandas"), ic=ics,
                   note="Spearman IC across only three ETFs per session; alphalens forward returns use raw closes.")
    elif a.arm == "sktime":
        from sktime.forecasting.theta import ThetaForecaster
        y = pd.Series(np.log(dev["SPY"].to_numpy()[-252:]))
        fc = ThetaForecaster(sp=1).fit(y).predict(fh=[1, 2, 3, 4, 5])
        out.update(version=importlib.metadata.version("sktime"), theta_forecast_log_close=[round(float(v), 6) for v in fc])
    elif a.arm == "tsfresh":
        from tsfresh import extract_features
        from tsfresh.feature_extraction import MinimalFCParameters
        tail = dev.iloc[-252:]
        long = pd.DataFrame({"id": np.repeat(tail.columns, len(tail)), "time": np.tile(np.arange(len(tail)), len(tail.columns)),
                             "value": np.concatenate([np.log(tail[c]).diff().fillna(0).to_numpy() for c in tail.columns])})
        feats = extract_features(long, column_id="id", column_sort="time", default_fc_parameters=MinimalFCParameters(), n_jobs=0, disable_progressbar=True)
        out.update(version=importlib.metadata.version("tsfresh"), features={i: {k: round(float(v), 8) for k, v in row.items()} for i, row in feats.iterrows()})
    elif a.arm == "river":
        from river import linear_model, preprocessing, metrics
        r = np.log(dev["SPY"]).diff().dropna().to_numpy()
        model = preprocessing.StandardScaler() | linear_model.LinearRegression()
        mae = metrics.MAE()
        for i in range(5, len(r)):
            x = {"lag" + str(k): r[i - k] for k in range(1, 6)}
            mae.update(r[i], model.predict_one(x))
            model.learn_one(x, r[i])
        naive = float(np.mean(np.abs(r[5:])))
        out.update(version=importlib.metadata.version("river"), progressive_mae=round(float(mae.get()), 8), naive_zero_mae=round(naive, 8), n=int(len(r) - 5))
    elif a.arm == "arcticdb":
        import arcticdb as adb
        a.tmp.mkdir(parents=True, exist_ok=False)
        lib = adb.Arctic("lmdb://" + str(a.tmp)).get_library("frozen", create_if_missing=True)
        lib.write("close", close)
        back = lib.read("close").data
        out.update(version=importlib.metadata.version("arcticdb"), rows=int(len(back)), roundtrip_equal=bool(back.equals(close)),
                   versions_listed=len(lib.list_versions("close")))
    else:
        raise SystemExit("unknown arm")
    print(json.dumps(out, sort_keys=True))


if __name__ == "__main__":
    main()
