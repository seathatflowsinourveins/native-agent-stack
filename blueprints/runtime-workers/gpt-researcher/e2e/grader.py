"""DRB-II transport adapter, never a local quality scorer.

Reference: imlrz/DeepResearch-Bench-II b38f360603db9531b102aef8c166cedb8509b6f6
run_evaluation.py:428-458,530-581. Preserve native scores, reject incomplete
transport, then call unchanged aggregate_scores.py for every metric.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import uuid
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from gateway import CHAT_URL, GatewayTransport, model_id

DIMENSIONS = ("info_recall", "analysis", "presentation")


def load_task(path, selection):
    """Keep the exact upstream JSONL row, including its original newline."""
    matches = []
    for raw in path.read_bytes().splitlines(keepends=True):
        if raw.strip():
            task = json.loads(raw)
            if task.get("idx") == selection["idx"]:
                matches.append((task, raw))
    if len(matches) != 1:
        raise ValueError("expected one frozen upstream task")
    task, raw = matches[0]
    if (hashlib.sha256(raw).hexdigest() != selection["row_sha256"]
            or hashlib.sha256(task["prompt"].encode("utf-8")).hexdigest() != selection["prompt_sha256"]):
        raise ValueError("frozen upstream task bytes changed")
    return task, raw


def verified_source(prefix):
    pins = json.loads((HERE.parent / "pins.json").read_text())["grader"]
    source = prefix / "grader-source" / ("DeepResearch-Bench-II-" + pins["commit"])
    for name, expected in pins["files"].items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != expected:
            raise ValueError("grader source differs from pin: " + name)
    return source


def validate_grade(rows, task, arm="gptr"):
    """Validate delivery and schema, including all-zero/blocked native scores."""
    try:
        if len(rows) != 1 or rows[0]["model"] != arm or rows[0]["idx"] != task["idx"]:
            raise ValueError("expected exactly one matching native result")
        result = rows[0]["result"]
        if "error" in result or result["task"] != task["content"]["task"]:
            raise ValueError("native evaluation failed or task mismatch")
        scores = result["scores"]
        if set(scores) != set(DIMENSIONS):
            raise ValueError("missing or unexpected rubric dimension")
        for dimension in DIMENSIONS:
            if set(scores[dimension]) != set(task["content"]["rubric"][dimension]):
                raise ValueError("missing or unexpected rubric item")
            for item in scores[dimension].values():
                if (set(item) != {"score", "reason", "evidence"}
                        or type(item["score"]) is not int or item["score"] not in (-1, 0, 1)
                        or not isinstance(item["reason"], str) or not isinstance(item["evidence"], str)):
                    raise ValueError("malformed native rubric result")
        return result
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("malformed native evaluator output") from error


def read_report(run_dir, idx, expected_sha256):
    """Bind the native result to the report bytes exported for that attempt."""
    report = (run_dir / "frozen-reports/gptr" / f"idx-{idx}.md").read_bytes()
    if (report != (run_dir / "report.md").read_bytes()
            or hashlib.sha256(report).hexdigest() != expected_sha256):
        raise ValueError("graded report bytes changed")
    return report


def read_grade(run_dir):
    """Re-read actual upstream rows/CSVs; do not trust a wrapper's success bit."""
    selection = json.loads((HERE / "task.json").read_text())
    task, _ = load_task(run_dir / "tasks-and-rubrics.jsonl", selection)
    result_path = run_dir / "drb-result.jsonl"
    rows = [json.loads(line) for line in result_path.read_text().splitlines() if line.strip()]
    validate_grade(rows, task)
    summary = json.loads((run_dir / "grade-summary.json").read_text())
    pin = json.loads((HERE.parent / "pins.json").read_text())["grader"]["commit"]
    if (summary["commit"] != pin or summary["idx"] != task["idx"]
            or summary["raw_result_sha256"] != hashlib.sha256(result_path.read_bytes()).hexdigest()):
        raise ValueError("native grade artifacts do not match their receipt")
    report = read_report(run_dir, task["idx"], summary["report_sha256"])
    worker_result = json.loads((run_dir / "result.json").read_text())
    if worker_result["report"].encode("utf-8") != report:
        raise ValueError("native scores are not for the current worker output")
    metrics = {}
    for suffix in ("inforecall", "analysis", "presentation", "total", "blocked"):
        path = run_dir / ("scores_" + suffix + ".csv")
        if summary["metric_artifacts"][path.name] != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError("native aggregate changed")
        with path.open(newline="") as handle:
            cases = [row for row in csv.DictReader(handle) if row["idx"] != "avg"]
        if len(cases) != 1 or cases[0]["idx"] != str(task["idx"]):
            raise ValueError("missing or extra aggregated task")
        metrics[suffix] = float(cases[0]["gptr"])
        if not 0 <= metrics[suffix] <= 1:
            raise ValueError("malformed upstream metric")
    return {"status": "graded", "harness": "DeepResearch-Bench-II", "commit": pin,
            "judge_model": model_id(summary["judge_model"]), "idx": task["idx"],
            "metrics_from_upstream_csv": metrics,
            "verdict": "upstream rubric scores; no local binary quality threshold"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--model", required=True, type=model_id)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    source = verified_source(args.prefix.resolve())
    selection = json.loads((HERE / "task.json").read_text())
    task, raw = load_task(source / "tasks_and_rubrics.jsonl", selection)
    if (run_dir / "tasks-and-rubrics.jsonl").read_bytes() != raw:
        raise ValueError("worker/grader frozen task mismatch")
    report_path = run_dir / "frozen-reports/gptr" / f"idx-{task['idx']}.md"
    report_sha256 = hashlib.sha256(report_path.read_bytes()).hexdigest()
    paper_chars = len(read_report(run_dir, task["idx"], report_sha256).decode("utf-8"))
    if not paper_chars:
        raise ValueError("empty exported report")
    result_path = run_dir / "drb-result.jsonl"
    if result_path.exists() or (run_dir / "grade-summary.json").exists():
        raise ValueError("use a fresh attempt; native evaluator appends outputs")
    # Both possible native dotenv locations are owned, freshly created paths.
    if any((p / ".env").exists() for p in (source, run_dir)):
        raise ValueError("grader does not load dotenv files")
    os.chdir(run_dir)
    os.environ.update(OPENAI_API_URL=CHAT_URL, OPENAI_API_KEY="local-loopback",
                      OPENAI_MODEL=args.model, OPENAI_REASONING_EFFORT="max",
                      OPENAI_MAX_OUTPUT_TOKENS="32768", OPENAI_TIMEOUT="600")
    sys.path.insert(0, str(source))
    import gpt_client
    transport = GatewayTransport(uuid.uuid4().hex, model=args.model,
                                 correlation_log=run_dir / "judge-correlations.jsonl")
    original_requests = gpt_client.requests
    # Change this client's transport only, not the shared requests module.
    gpt_client.requests = SimpleNamespace(post=transport.grader_post(original_requests.post))
    original_argv = sys.argv
    try:
        sys.argv = [str(source / "run_evaluation.py"), "--pdf_dir", str(run_dir / "frozen-reports"),
                    "--tasks_jsonl", str(run_dir / "tasks-and-rubrics.jsonl"),
                    "--out_jsonl", str(result_path), "--max_workers", "1", "--max_retries", "5",
                    "--chunk_size", "50", "--max_paper_chars", str(paper_chars),
                    "--log_file", str(run_dir / "grader-native.log")]
        runpy.run_path(str(source / "run_evaluation.py"), run_name="__main__")
        rows = [json.loads(line) for line in result_path.read_text().splitlines() if line.strip()]
        validate_grade(rows, task)
        sys.argv = [str(source / "aggregate_scores.py"), "--input", str(result_path),
                    "--tasks-file", str(run_dir / "tasks-and-rubrics.jsonl"),
                    "--output-prefix", str(run_dir / "scores")]
        runpy.run_path(str(source / "aggregate_scores.py"), run_name="__main__")
    finally:
        gpt_client.requests = original_requests
        sys.argv = original_argv
    # Retain upstream CSVs as the metric authority. No local threshold or score.
    summary = {"status": "graded", "harness": "DeepResearch-Bench-II",
               "commit": json.loads((HERE.parent / "pins.json").read_text())["grader"]["commit"],
               "judge_model": args.model, "idx": task["idx"],
               "verdict": "upstream rubric scores; no benchmark-wide binary pass threshold",
               "report_sha256": report_sha256,
               "metric_artifacts": {}, "raw_result_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest()}
    for suffix in ("inforecall", "analysis", "presentation", "total", "blocked"):
        path = run_dir / ("scores_" + suffix + ".csv")
        if not path.is_file() or not path.stat().st_size:
            raise ValueError("missing native aggregate output")
        summary["metric_artifacts"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (run_dir / "grade-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
