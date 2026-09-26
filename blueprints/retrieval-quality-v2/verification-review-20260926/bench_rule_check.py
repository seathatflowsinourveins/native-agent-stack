"""Applies run.py's qmd bench completeness rule to a committed run's retained `qmd bench` output.

Loads run.py from the blueprint directory, rebuilds the benchmark fixture from queries.json exactly
as run.py does, takes the `native_bench` record's stdout from native-<run-id>.json, checks it
against the stdout sha256 that record and the receipt keep, and prints what
bench_output_problems() finds (an empty list means the output covers the fixture).
Standard library only; reads committed files and runs nothing else.

Usage: python3 bench_rule_check.py [<run-id>]   (default 20260926T024558Z)
"""
import hashlib
import importlib.util
import json
import pathlib
import sys

BLUEPRINT = pathlib.Path(__file__).resolve().parent.parent
RUN_ID = sys.argv[1] if len(sys.argv) > 1 else "20260926T024558Z"

spec = importlib.util.spec_from_file_location("rqv2_run", BLUEPRINT / "run.py")
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)

queries = json.loads((BLUEPRINT / "queries.json").read_text(encoding="utf-8"))["queries"]
fixture = run.build_bench_fixture(queries)
fixture_bytes = (json.dumps(fixture, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
receipt = json.loads((BLUEPRINT / f"results-{RUN_ID}.json").read_text(encoding="utf-8"))
native = json.loads((BLUEPRINT / f"native-{RUN_ID}.json").read_text(encoding="utf-8"))
record = next(r for r in native["records"] if r["id"] == "native_bench")
stdout = record["stdout"]
doc = json.loads(stdout)
print(json.dumps({
    "run_id": RUN_ID,
    "run_py_sha256": hashlib.sha256((BLUEPRINT / "run.py").read_bytes()).hexdigest(),
    "fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
    "receipt_fixture_sha256": receipt["native_bench"]["fixture"]["sha256"],
    "stdout_sha256": hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
    "record_stdout_sha256": record["stdout_sha256"],
    "receipt_stdout_sha256": receipt["native_bench"]["stdout_sha256"],
    "stdout_identical_to_raw": record["stdout_identical_to_raw"],
    "receipt_status": receipt["native_bench"]["status"],
    "results": len(doc["results"]),
    "fixture_queries": len(fixture["queries"]),
    "summary_backends": sorted(doc["summary"]),
    "problems": run.bench_output_problems(doc, fixture),
}, indent=2))
