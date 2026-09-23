#!/usr/bin/env python3
"""Run a real skfolio optimizer (MeanRisk, MINIMIZE_RISK/Variance, and
HierarchicalRiskParity/HRP) over the SAME 252/63/6 WalkForward split on the
frozen SPY/QQQ/IWM inputs pinned in blueprints/us-equities/research-evaluation/
plan.json, using the receipt's own Python 3.13.15 environment (the venv built
from requirements.lock with --require-hashes --offline). Records out-of-sample
(development cross_val_predict + a held-out 2021Q1 reserved fit/predict) results.

This is a distinct metric from evaluate.py's 5-session raw-price label (daily
close-to-close returns fed to skfolio's own risk/return machinery, not the
custom episodic label), preregistered as: development WalkForward cross_val_predict
annualized return/vol/Sharpe per optimizer, plus a reserved-segment (fit on the
last 252+6 development sessions, predict on 2021Q1) out-of-sample return/vol/Sharpe
per optimizer. No claim of superiority is made; this only establishes that a real
skfolio optimizer (not only the WalkForward splitter) executes on this layer's
frozen inputs.
"""
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL_DIR = Path("/tmp/session-scratchpad/skf_eval")


def load_evaluate_module():
    spec = importlib.util.spec_from_file_location("research_evaluate", EVAL_DIR / "evaluate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean-source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    import numpy as np
    import pandas as pd
    import skfolio
    from skfolio.model_selection import WalkForward, cross_val_predict
    from skfolio.optimization import HierarchicalRiskParity, MeanRisk
    from skfolio.preprocessing import prices_to_returns

    if importlib.metadata.version("skfolio") != "1.3.0":
        raise ValueError("use the accepted skfolio version")

    ev = load_evaluate_module()
    root, out = args.lean_source.resolve(), args.out.resolve()
    if out.exists():
        raise ValueError("use a fresh output directory")
    out.mkdir(parents=True, mode=0o700)

    plan = json.loads((EVAL_DIR / "plan.json").read_text())
    plan_sha256 = digest(EVAL_DIR / "plan.json")
    if plan_sha256 != "b8d1beba6eddd0388957ca0d9e9c46ebfb2ca538f076419d5a8dcaaaf82be4a7":
        raise ValueError("plan.json is not the frozen file the receipt scored")

    input_receipt = ev.verify_inputs(root, plan["inputs"])
    panel, dates, auxiliary, counts = ev.load_panel(root, plan)
    eligible = [i for i, d in enumerate(dates) if plan["eligible_start"] <= d <= plan["development_end"]]
    reserved = [i for i, d in enumerate(dates) if plan["reserved_start"] <= d <= plan["reserved_end"]]
    assets = plan["assets"]

    def price_frame(indices):
        idx = pd.to_datetime([dates[i] for i in indices])
        data = {a: [float(panel[a][i]["close"]) for i in indices] for a in assets}
        return pd.DataFrame(data, index=idx)

    dev_prices = price_frame(eligible)
    dev_returns = prices_to_returns(dev_prices)

    spec = plan["splitter"]
    cv = WalkForward(**{k: spec[k] for k in ["train_size", "test_size", "purged_size", "reduce_test"]})

    def annualize(ret_series):
        ret_series = np.asarray(ret_series, dtype=float)
        mean_d, std_d = float(np.mean(ret_series)), float(np.std(ret_series, ddof=1)) if len(ret_series) > 1 else 0.0
        ann_return = (1 + mean_d) ** 252 - 1
        ann_vol = std_d * (252 ** 0.5)
        sharpe = (mean_d / std_d) * (252 ** 0.5) if std_d > 0 else None
        return {"n_observations": int(len(ret_series)), "mean_daily_return": mean_d,
                "annualized_return_approx": ann_return, "annualized_vol_approx": ann_vol,
                "annualized_sharpe_approx": sharpe}

    optimizers = {
        "mean_risk_min_variance": MeanRisk(),
        "hrp_variance": HierarchicalRiskParity(),
    }

    results = {"skfolio_version": skfolio.__version__, "plan_sha256": plan_sha256,
               "splitter_params": {k: spec[k] for k in ["train_size", "test_size", "purged_size", "reduce_test"]},
               "assets": assets, "development": {}, "reserved": {}}

    for name, est in optimizers.items():
        pop = cross_val_predict(est, dev_returns, cv=cv, n_jobs=None)
        port_returns = pop.returns
        results["development"][name] = dict(
            annualize(port_returns),
            n_test_folds=len(pop.portfolios) if hasattr(pop, "portfolios") else None,
        )

    reserved_train_idx = eligible[-(spec["train_size"] + spec["purged_size"]):-spec["purged_size"]]
    reserved_train_prices = price_frame(reserved_train_idx)
    reserved_test_prices = price_frame(reserved)
    reserved_train_returns = prices_to_returns(reserved_train_prices)
    reserved_test_returns = prices_to_returns(reserved_test_prices)

    for name, est_cls in [("mean_risk_min_variance", MeanRisk), ("hrp_variance", HierarchicalRiskParity)]:
        est = est_cls()
        est.fit(reserved_train_returns)
        weights = {a: float(w) for a, w in zip(reserved_train_returns.columns, est.weights_)}
        test_port_returns = (reserved_test_returns * est.weights_).sum(axis=1)
        results["reserved"][name] = {
            "fit_weights": weights,
            "fit_train_first": str(reserved_train_prices.index[0].date()),
            "fit_train_last": str(reserved_train_prices.index[-1].date()),
            "test_first": str(reserved_test_prices.index[1].date()),
            "test_last": str(reserved_test_prices.index[-1].date()),
            **annualize(test_port_returns.to_numpy()),
        }

    unchanged = ev.verify_inputs(root, plan["inputs"]) == input_receipt
    results["inputs_unchanged"] = unchanged
    (out / "results.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"development": results["development"], "reserved": results["reserved"],
                       "inputs_unchanged": unchanged}, indent=2))


if __name__ == "__main__":
    main()
