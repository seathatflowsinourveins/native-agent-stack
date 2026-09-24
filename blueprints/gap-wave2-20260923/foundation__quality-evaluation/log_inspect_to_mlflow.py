#!/usr/bin/env python3
"""Log Inspect JSON eval logs to an MLflow tracking server as one run each.

Usage: log_inspect_to_mlflow.py TRACKING_URI OUT_JSON LOG.json [LOG.json ...]
"""
import json
import sys

import mlflow

uri, out, logs = sys.argv[1], sys.argv[2], sys.argv[3:]
mlflow.set_tracking_uri(uri)
mlflow.set_experiment("gap-wave2-quality-evaluation")
runs = []
for path in logs:
    log = json.load(open(path))
    ev = log["eval"]
    with mlflow.start_run(run_name=ev["task"]) as run:
        mlflow.log_params({"task": ev["task"], "model": ev["model"], "inspect_version": log["eval"].get("packages", {}).get("inspect_ai", ""),
                           "samples": len(log.get("samples") or []), "inspect_status": log["status"]})
        for score in log["results"]["scores"]:
            for name, metric in score["metrics"].items():
                mlflow.log_metric(f"{score['name']}.{name}", metric["value"])
        for model, usage in (log["stats"].get("model_usage") or {}).items():
            for key in ("input_tokens", "output_tokens", "total_tokens"):
                if usage.get(key) is not None:
                    mlflow.log_metric(f"usage.{key}", usage[key])
        mlflow.log_artifact(path)
        runs.append({"run_id": run.info.run_id, "task": ev["task"], "log": path.rsplit("/", 1)[-1]})
json.dump(runs, open(out, "w"), indent=1)
print(json.dumps(runs))
