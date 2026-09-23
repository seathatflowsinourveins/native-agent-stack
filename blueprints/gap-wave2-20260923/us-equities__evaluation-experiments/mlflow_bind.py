"""Gap 8: run the unchanged research-evaluation/evaluate.py inside an MLflow 3.16.1 run
(temp sqlite store), log params/metrics/dataset hashes, then read back with
mlflow.search_runs and compare. Usage (from the mlflow venv):
  mlflow_bind.py REPO LEAN_SOURCE SKFOLIO_PYTHON WORKDIR > readback.json
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import mlflow
from mlflow.data.meta_dataset import MetaDataset
from mlflow.data.http_dataset_source import HTTPDatasetSource
from mlflow.tracking import MlflowClient

repo, lean, skpy, work = map(Path, sys.argv[1:5])
blue = repo / "blueprints/us-equities/research-evaluation"
plan = json.loads((blue / "plan.json").read_text())
work.mkdir(parents=True, exist_ok=False)
mlflow.set_tracking_uri("sqlite:///" + str(work / "mlflow.db"))
mlflow.set_experiment("research-evaluation-chronological-controls")
LEAN_COMMIT = "985ef30ad3ac774218c5ac516b4cb0aa2655730f"

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

params = {"plan_id": plan["id"], "plan_sha256": sha(blue / "plan.json"), "evaluate_py_sha256": sha(blue / "evaluate.py"),
          "requirements_lock_sha256": sha(blue / "requirements.lock"), "assets": ",".join(plan["assets"]),
          "lookbacks": ",".join(map(str, plan["lookbacks"])), "candidates": ",".join(plan["candidates"]),
          "round_trip_cost_fraction": plan["round_trip_cost_fraction"],
          "train_size": plan["splitter"]["train_size"], "test_size": plan["splitter"]["test_size"],
          "purged_size": plan["splitter"]["purged_size"], "reduce_test": plan["splitter"]["reduce_test"],
          "eligible_start": plan["eligible_start"], "development_end": plan["development_end"],
          "reserved_start": plan["reserved_start"], "reserved_end": plan["reserved_end"]}
with mlflow.start_run(run_name="chronological-controls-replay") as run:
    mlflow.log_params(params)
    for name, digest in plan["inputs"].items():
        mlflow.set_tag("input_sha256:" + name, digest)
        dataset = MetaDataset(source=HTTPDatasetSource(f"https://github.com/QuantConnect/Lean/raw/{LEAN_COMMIT}/{name}"),
                              name=name, digest=digest[:36])  # MLflow caps dataset digest at 36 chars; full sha256 is in the tag
        mlflow.log_input(dataset, context="input")
    out = work / "run-1"
    proc = subprocess.run([str(skpy), str(blue / "evaluate.py"), "--lean-source", str(lean), "--out", str(out)],
                          capture_output=True, text=True, timeout=900)
    (work / "evaluate.stdout.txt").write_text(proc.stdout); (work / "evaluate.stderr.txt").write_text(proc.stderr)
    mlflow.log_metric("evaluate_exit_code", proc.returncode)
    if proc.returncode != 0:
        raise SystemExit("evaluate.py failed: " + proc.stderr[-2000:])
    result = json.loads((out / "results.json").read_text())
    metrics = {"development_folds": len(result["development_folds"]), "ledger_records": result["ledger_records"],
               "inputs_unchanged": int(result["inputs_unchanged"])}
    for cand, summ in result["reserved"]["all_candidates"].items():
        metrics[f"reserved.{cand}.mean_raw_price_label"] = float(summ["mean_raw_price_label"])
        metrics[f"reserved.{cand}.mean_net_cost_proxy_label"] = float(summ["mean_net_cost_proxy_label"])
        metrics[f"reserved.{cand}.observed_episodes"] = summ["observed_episodes"]
    mlflow.log_metrics(metrics)
    mlflow.set_tags({"reserved_chosen": result["reserved"]["chosen"], "ledger_sha256": result["ledger_sha256"],
                     "freeze_sha256": result["freeze_sha256"], "results_sha256": sha(out / "results.json"),
                     "no_pnl_or_execution_claim": str(result["no_pnl_or_execution_claim"])})
    mlflow.log_artifact(str(out / "results.json")); mlflow.log_artifact(str(out / "freeze.json"))
    run_id = run.info.run_id

# Readback.
frame = mlflow.search_runs(experiment_names=["research-evaluation-chronological-controls"])
row = frame.iloc[0]
def compare(expected_metrics):
    mism = []
    for k, v in params.items():
        if str(row["params." + k]) != str(v): mism.append(("param", k))
    for k, v in expected_metrics.items():
        if float(row["metrics." + k]) != float(v): mism.append(("metric", k))
    for name, digest in plan["inputs"].items():
        if row["tags.input_sha256:" + name] != digest: mism.append(("tag", name))
    return mism
client = MlflowClient()
inputs = client.get_run(run_id).inputs.dataset_inputs
ds = {d.dataset.name: d.dataset.digest for d in inputs}
# Fix round 1: compare every logged metric, including evaluate_exit_code.
logged_metrics = dict(metrics, evaluate_exit_code=proc.returncode)
probe = dict(logged_metrics); probe["ledger_records"] = metrics["ledger_records"] + 1
probe_exit = dict(logged_metrics); probe_exit["evaluate_exit_code"] = 999
metric_columns = sorted(c.removeprefix("metrics.") for c in frame.columns if c.startswith("metrics."))
print(json.dumps({
    "runs_found": len(frame), "status": row["status"], "evaluate_exit_code": proc.returncode,
    "params_logged": len(params), "metrics_logged": len(logged_metrics),
    "metric_columns_read_back": len(metric_columns),
    "all_read_back_metrics_compared": metric_columns == sorted(logged_metrics),
    "readback_mismatches": compare(logged_metrics),
    "negative_probe_changed_ledger_records_detected": compare(probe) == [("metric", "ledger_records")],
    "negative_probe_exit_code_999_detected": compare(probe_exit) == [("metric", "evaluate_exit_code")],
    "dataset_inputs": len(ds), "dataset_digests_equal_plan_prefix36": ds == {k: v[:36] for k, v in plan["inputs"].items()},
    "first_attempt_note": "full 64-hex sha256 as dataset digest was rejected: 'digest' exceeds the maximum length of 36 characters",
    "dataset_digest_lengths": sorted({len(v) for v in ds.values()}),
    "tags": {k: row["tags." + k] for k in ("reserved_chosen", "ledger_sha256", "freeze_sha256", "results_sha256")},
    "artifacts": sorted(a.path for a in client.list_artifacts(run_id)),
    "evaluate_stdout": json.loads(proc.stdout), "result_versions": result["versions"],
    "metrics": metrics,
}, indent=1, default=str))
