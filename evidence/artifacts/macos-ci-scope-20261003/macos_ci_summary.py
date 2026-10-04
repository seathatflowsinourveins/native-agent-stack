"""Summarize macos-ci-evidence.json: per-job queue and run minutes, failing jobs and steps, macOS-only failures."""
import collections
import json
import pathlib

d = json.loads(pathlib.Path(__file__).with_name("macos-ci-evidence.json").read_text())
print("since", d["since"], "calls", d["api_calls"], "bootstrap runs", d["bootstrap_runs"], "validate runs",
      d["validate_runs"], "jobs fetched for", d["runs_with_jobs_fetched"], "runs; conclusions", d["bootstrap_conclusions"])
for name, v in d["jobs"].items():
    q, r = v["queue"] or {}, v["run"] or {}
    print(f'{name:22} queue med {q.get("median")} p90 {q.get("p90")} max {q.get("max")} | run med {r.get("median")} '
          f'p90 {r.get("p90")} max {r.get("max")} sum {r.get("sum")} | {v["conclusions"]}')
failed_job_count = collections.Counter()
step_count = collections.Counter()
mac_only = set(d["macos_only_failures_linux_green"])
for f in d["failures"]:
    for j in f["failed_jobs"]:
        failed_job_count[j["job"]] += 1
        if f["run_id"] in mac_only:
            step_count[(j["job"], j["step"])] += 1
print("failed jobs, all failures:", dict(failed_job_count))
print("macOS-only failures (Linux validate green on the same SHA), by job and step:")
for (job, step), n in step_count.most_common(25):
    print(f"  {n:3d} {job} :: {step}")
outcomes = collections.Counter(tuple(sorted(set(x or "none" for x in f["linux_validate_same_sha"])))
                               for f in d["failures"] if f["run_id"] in mac_only)
print("Linux validate outcomes for those SHAs:", dict(outcomes))
days = collections.Counter(f["created"][:10] for f in d["failures"] if f["run_id"] in mac_only)
print("macOS-only failures by day:", dict(sorted(days.items())))
branches = collections.Counter(f["branch"] for f in d["failures"] if f["run_id"] in mac_only)
print("distinct branches:", len(branches))
