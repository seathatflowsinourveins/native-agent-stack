"""Minimal local mteb 2.21.0 evaluation: one small public task, one small public model, CPU.

Usage: mteb_minimal.py OUTDIR. Result cache and HF downloads go to caller-set temp dirs.
"""
import json
import sys
import time
from pathlib import Path

import mteb
import torch

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
task = mteb.get_tasks(tasks=["STSBenchmark"])[0]
meta = mteb.get_model_meta("sentence-transformers/all-MiniLM-L6-v2")
model = mteb.get_model(meta.name, revision=meta.revision, device="cpu")
start = time.monotonic()
result = mteb.evaluate(model, task, co2_tracker=False, cache=mteb.ResultCache(cache_path=out / "cache"),
                       show_progress_bar=False, overwrite_strategy="always")
elapsed = time.monotonic() - start
task_result = result.task_results[0]
scores = task_result.scores["test"][0]
summary = {"mteb": mteb.__version__ if hasattr(mteb, "__version__") else None, "torch": torch.__version__,
           "cuda_available": torch.cuda.is_available(), "task": task.metadata.name,
           "task_dataset": task.metadata.dataset, "model": meta.name, "model_revision": meta.revision,
           "split": "test", "main_score": scores["main_score"],
           "cosine_spearman": scores.get("cosine_spearman"), "evaluation_seconds": round(elapsed, 2)}
(out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
print(json.dumps(summary, indent=1))
