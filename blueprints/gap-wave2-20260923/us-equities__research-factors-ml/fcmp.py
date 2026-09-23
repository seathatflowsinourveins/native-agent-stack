#!/usr/bin/env python3
"""Matched 5-session forecast comparison on the frozen research-evaluation series.

Arms: naive, statsforecast AutoARIMA, statsmodels ARIMA(1,1,1), chronos-bolt-small,
Kronos-small. Folds are skfolio WalkForward(252, 63, purged 6, reduce_test) over
eligible development sessions (as evaluate.py) plus the reserved 2021Q1 segment.
Origins: global stride-5 episode decisions t inside each test fold with t+5 inside
the segment. Context: 252 sessions ending at t. Target r = ln(close[t+5]/close[t]).
Primary metric: per-fold MAE over origins x assets. See preregistration.json.
"""
import argparse
import csv
import datetime as dt
from decimal import Decimal
import hashlib
import importlib.metadata
import io
import json
import math
from pathlib import Path
import sys
import time
import warnings
import zipfile

REPO = Path(__file__).resolve().parents[3]
EVAL_DIR = REPO / "blueprints/us-equities/research-evaluation"
sys.path.insert(0, str(EVAL_DIR))
import evaluate as ev  # noqa: E402

CONTEXT, H = 252, 5
PINS = {"chronos": ("amazon/chronos-bolt-small", "772f3d25d38aec6d914c8949dab4462e2d46f5d8"),
        "kronos_model": ("NeoQuasar/Kronos-small", "901c26c1332695a2a8f243eb2f37243a37bea320"),
        "kronos_tokenizer": ("NeoQuasar/Kronos-Tokenizer-base", "0e0117387f39004a9016484a186a908917e22426")}


def load_ohlcv(root, plan, panel):
    out = {}
    for asset in plan["assets"]:
        with zipfile.ZipFile(root / ("Data/equity/usa/daily/" + asset.lower() + ".zip")) as z:
            rows = list(csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())))
        recs = []
        for r in rows:
            d = dt.datetime.strptime(r[0], "%Y%m%d %H:%M").date().isoformat()
            if plan["data_start"] <= d <= plan["reserved_end"]:
                o, h, l, c = [float(Decimal(x) / 10000) for x in r[1:5]]
                recs.append({"date": d, "open": o, "high": h, "low": l, "close": c, "volume": float(r[5])})
        ref = panel[asset]
        if [x["date"] for x in recs] != [x["date"] for x in ref] or any(
                abs(a["close"] - float(b["close"])) > 1e-9 or abs(a["open"] - float(b["open"])) > 1e-9 for a, b in zip(recs, ref)):
            raise ValueError("OHLCV loader disagrees with evaluate.load_panel")
        out[asset] = recs
    return out


def build_origins(plan, dates):
    from skfolio.model_selection import WalkForward
    import pandas as pd
    eligible = [i for i, d in enumerate(dates) if plan["eligible_start"] <= d <= plan["development_end"]]
    reserved = [i for i, d in enumerate(dates) if plan["reserved_start"] <= d <= plan["reserved_end"]]
    anchor = eligible[0]
    frame = pd.DataFrame({"s": [dates[i] for i in eligible]}, index=pd.to_datetime([dates[i] for i in eligible]))
    folds = []
    for j, (_train, test) in enumerate(WalkForward(train_size=252, test_size=63, purged_size=6, reduce_test=True).split(frame)):
        folds.append(("development-" + str(j + 1), [eligible[int(i)] for i in test], eligible[-1]))
    folds.append(("reserved-2021q1", reserved, reserved[-1]))
    result = []
    for name, test, seg_last in folds:
        origins = [t for t in test if (t - anchor) % 5 == 0 and t + H <= seg_last and t - CONTEXT + 1 >= 0]
        result.append({"fold": name, "test_first": dates[test[0]], "test_last": dates[test[-1]], "origins": origins})
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--lean-source", type=Path, required=True)
    p.add_argument("--kronos-src", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--kronos-samples", type=int, default=20)
    p.add_argument("--models", default="naive,statsforecast_autoarima,statsmodels_arima111,chronos_bolt_small,kronos_small")
    p.add_argument("--kronos-device", default="cpu")
    p.add_argument("--sf-jobs", type=int, default=-1)
    p.add_argument("--merge", type=Path, nargs="*", help="forecasts.json files to merge instead of running models")
    args = p.parse_args()
    wanted = args.models.split(",")
    import numpy as np
    import pandas as pd
    import torch
    args.out.mkdir(parents=True, exist_ok=False)
    root = args.lean_source.resolve()
    plan = json.loads((EVAL_DIR / "plan.json").read_text())
    inputs = ev.verify_inputs(root, plan["inputs"])
    panel, dates, _aux, _counts = ev.load_panel(root, plan)
    ohlcv = load_ohlcv(root, plan, panel)
    folds = build_origins(plan, dates)
    assets = plan["assets"]
    tasks = []  # (fold, asset, t)
    for f in folds:
        for t in f["origins"]:
            for a in assets:
                tasks.append((f["fold"], a, t))
    close = {a: np.array([r["close"] for r in ohlcv[a]]) for a in assets}
    logc = {a: np.log(close[a]) for a in assets}
    truth = np.array([logc[a][t + H] - logc[a][t] for _, a, t in tasks])
    preds, timing, source_meta = {}, {}, {}

    if args.merge:
        keys = [(f, a, dates[t], dates[t + H]) for f, a, t in tasks]
        for path in args.merge:
            rows = json.loads(path.read_text())
            if [(r["fold"], r["asset"], r["decision"], r["target"]) for r in rows] != keys or any(abs(r["r"] - truth[i]) > 1e-12 for i, r in enumerate(rows)):
                raise ValueError("merge keys/targets differ: " + str(path))
            for m in rows[0]:
                if m not in ("fold", "asset", "decision", "target", "r"):
                    if m in preds:
                        raise ValueError("duplicate model " + m)
                    preds[m] = np.array([r[m] for r in rows])
            src = json.loads((path.parent / "results.json").read_text())
            source_meta[str(path)] = {"models_run": src.get("models_run"), "kronos_device": src.get("kronos_device"),
                                      "kronos_samples": src.get("kronos_samples"), "timing_s": src.get("timing_s")}
        wanted = []
    if "naive" in wanted:
        preds["naive"] = np.zeros(len(tasks))

    t0 = time.time()
    if "statsforecast_autoarima" in wanted:
      from statsforecast import StatsForecast
      from statsforecast.models import AutoARIMA
      long = pd.DataFrame({"unique_id": np.repeat(np.arange(len(tasks)), CONTEXT),
                           "ds": np.tile(np.arange(CONTEXT), len(tasks)),
                           "y": np.concatenate([logc[a][t - CONTEXT + 1:t + 1] for _, a, t in tasks])})
      fc = StatsForecast(models=[AutoARIMA(season_length=1)], freq=1, n_jobs=args.sf_jobs).forecast(df=long, h=H)
      fc = fc.sort_values(["unique_id", "ds"])
      last = fc.groupby("unique_id")["AutoARIMA"].last().reindex(np.arange(len(tasks))).to_numpy()
      preds["statsforecast_autoarima"] = last - np.array([logc[a][t] for _, a, t in tasks])
      timing["statsforecast_autoarima"] = time.time() - t0

    t0 = time.time()
    if "statsmodels_arima111" in wanted:
      from statsmodels.tsa.arima.model import ARIMA
      sm = []
      with warnings.catch_warnings():
          warnings.simplefilter("ignore")
          for _, a, t in tasks:
              y = logc[a][t - CONTEXT + 1:t + 1]
              res = ARIMA(y, order=(1, 1, 1), trend="n").fit()
              sm.append(res.forecast(H)[-1] - y[-1])
      preds["statsmodels_arima111"] = np.array(sm)
      timing["statsmodels_arima111"] = time.time() - t0

    t0 = time.time()
    if "chronos_bolt_small" in wanted:
      from chronos import BaseChronosPipeline
      pipe = BaseChronosPipeline.from_pretrained(PINS["chronos"][0], revision=PINS["chronos"][1], device_map="cpu", torch_dtype=torch.float32)
      ch = []
      for i in range(0, len(tasks), 256):
          batch = [torch.tensor(close[a][t - CONTEXT + 1:t + 1], dtype=torch.float32) for _, a, t in tasks[i:i + 256]]
          q, _mean = pipe.predict_quantiles(batch, prediction_length=H, quantile_levels=[0.1, 0.5, 0.9])
          ch.extend(q[:, H - 1, 1].tolist())
      preds["chronos_bolt_small"] = np.log(np.array(ch)) - np.array([logc[a][t] for _, a, t in tasks])
      timing["chronos_bolt_small"] = time.time() - t0

    t0 = time.time()
    if "kronos_small" in wanted:
      sys.path.insert(0, str(args.kronos_src))
      from model import Kronos, KronosTokenizer, KronosPredictor
      torch.manual_seed(0)
      np.random.seed(0)
      tok = KronosTokenizer.from_pretrained(PINS["kronos_tokenizer"][0], revision=PINS["kronos_tokenizer"][1])
      mdl = Kronos.from_pretrained(PINS["kronos_model"][0], revision=PINS["kronos_model"][1])
      tok.eval(); mdl.eval()
      predictor = KronosPredictor(mdl, tok, device=args.kronos_device, max_context=512)
      kr = []
      per_fold = {}
      for f_name, a, t in tasks:
          per_fold.setdefault(f_name, []).append((a, t))
      for f_name, items in per_fold.items():
          dfs, xts, yts = [], [], []
          for a, t in items:
              rows = ohlcv[a][t - CONTEXT + 1:t + 1]
              dfs.append(pd.DataFrame(rows)[["open", "high", "low", "close", "volume"]])
              xts.append(pd.Series(pd.to_datetime([r["date"] for r in rows])))
              yts.append(pd.Series(pd.to_datetime(dates[t + 1:t + H + 1])))
          with torch.no_grad():
              out = predictor.predict_batch(dfs, xts, yts, pred_len=H, T=1.0, top_p=0.9, sample_count=args.kronos_samples, verbose=False)
          for (a, t), o in zip(items, out):
              kr.append(math.log(float(o["close"].iloc[H - 1])) - logc[a][t])
      preds["kronos_small"] = np.array(kr)
      timing["kronos_small"] = time.time() - t0

    models = list(preds)
    fold_names = [f["fold"] for f in folds]
    per = {m: {} for m in models}
    for m in models:
        err = preds[m] - truth
        for fn in fold_names:
            idx = [i for i, (f, _, _) in enumerate(tasks) if f == fn]
            e = err[idx]
            per[m][fn] = {"n": len(idx), "mae": float(np.mean(np.abs(e))), "rmse": float(np.sqrt(np.mean(e ** 2)))}
    dev = [fn for fn in fold_names if fn.startswith("development")]
    rng = np.random.default_rng(20260923)
    boot_idx = rng.integers(0, len(dev), size=(10000, len(dev)))

    def interval(a, b):
        d = np.array([per[a][fn]["mae"] - per[b][fn]["mae"] for fn in dev])
        means = d[boot_idx].mean(axis=1)
        lo, hi = np.percentile(means, [2.5, 97.5])
        return {"mean_diff": float(d.mean()), "ci95": [float(lo), float(hi)], "folds_a_better": int((d < 0).sum()),
                "verdict": "a_better" if hi < 0 else "b_better" if lo > 0 else "no_difference_resolved"}

    pairs = [(m, "naive") for m in models if m != "naive"] + [
        ("chronos_bolt_small", "statsforecast_autoarima"), ("statsmodels_arima111", "statsforecast_autoarima"),
        ("chronos_bolt_small", "statsmodels_arima111"), ("kronos_small", "chronos_bolt_small")]
    pairs = [(a, b) for a, b in pairs if a in preds and b in preds]
    ratio_naive = "naive" in preds
    summary = {m: {"dev_mean_fold_mae": float(np.mean([per[m][fn]["mae"] for fn in dev])),
                   "reserved_mae": per[m]["reserved-2021q1"]["mae"],
                   "dev_mean_mae_ratio_to_naive": (float(np.mean([per[m][fn]["mae"] / per["naive"][fn]["mae"] for fn in dev])) if ratio_naive else None)}
               for m in models}
    forecasts = [{"fold": f, "asset": a, "decision": dates[t], "target": dates[t + H], "r": float(truth[i]),
                  **{m: float(preds[m][i]) for m in models}} for i, (f, a, t) in enumerate(tasks)]
    (args.out / "forecasts.json").write_text(json.dumps(forecasts, indent=1) + "\n")
    result = {"plan_sha256": ev.digest(EVAL_DIR / "plan.json"), "runner_sha256": ev.digest(__file__),
              "inputs_unchanged": ev.verify_inputs(root, plan["inputs"]) == inputs,
              "versions": {k: importlib.metadata.version(k) for k in ["statsforecast", "statsmodels", "chronos-forecasting", "torch", "skfolio", "pandas", "numpy"]},
              "pins": PINS, "kronos_samples": (None if args.merge else args.kronos_samples), "kronos_device": (None if args.merge else args.kronos_device),
              "models_run": wanted, "merge_source_metadata": source_meta,
              "merged_from": [str(x) for x in (args.merge or [])], "merged_sha256": [ev.digest(x) for x in (args.merge or [])],
              "folds": [{k: v for k, v in f.items() if k != "origins"} | {"origins": len(f["origins"])} for f in folds],
              "tasks": len(tasks), "per_fold": per, "summary": summary,
              "pairwise_dev_bootstrap": {a + "_vs_" + b: interval(a, b) for a, b in pairs},
              "timing_s": timing, "forecasts_sha256": ev.digest(args.out / "forecasts.json")}
    (args.out / "results.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"tasks": len(tasks), "summary": summary, "pairwise": result["pairwise_dev_bootstrap"],
                      "timing_s": timing, "inputs_unchanged": result["inputs_unchanged"],
                      "results_sha256": ev.digest(args.out / "results.json")}, indent=1))


if __name__ == "__main__":
    main()
