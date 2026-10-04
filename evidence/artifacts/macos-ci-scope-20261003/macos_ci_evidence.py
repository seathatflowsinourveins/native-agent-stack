"""macOS CI cost and benefit evidence from the GitHub Actions API, gathered once so analysts do not spend the
shared REST quota. Writes macos-ci-evidence.json next to this script and prints a summary.

Cost: queue and run minutes of every job in adoption-bootstrap.yml runs (validate-macos, bootstrap-macos,
bootstrap-macos-brew, bootstrap-linux, changes) since SINCE.
Benefit: every failed adoption-bootstrap run whose failing job is a macOS job, with the same head SHA's Linux
`validate` outcome (from the "Validate published evidence" workflow), so macOS-only failures can be classified.
"""
import collections
import datetime as dt
import json
import pathlib
import statistics
import subprocess
import sys

REPO = "seathatflowsinourveins/native-agent-stack"
SINCE = sys.argv[1] if len(sys.argv) > 1 else "2026-09-20"
MAX_JOB_CALLS = int(sys.argv[2]) if len(sys.argv) > 2 else 260
calls = 0


def api(path):
    global calls
    calls += 1
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"gh api failed ({path}): {r.stderr.strip()[:300]}")
    return json.loads(r.stdout)


def runs(workflow):
    out, page = [], 1
    while True:
        d = api(f"repos/{REPO}/actions/workflows/{workflow}/runs?per_page=100&page={page}&created=%3E%3D{SINCE}")
        out += d.get("workflow_runs", [])
        if len(d.get("workflow_runs", [])) < 100 or page >= 10:
            return out
        page += 1


def t(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


boot = runs("adoption-bootstrap.yml")
val = runs("validate.yml") if True else []
lin = {}
for r in val:
    lin.setdefault(r["head_sha"], []).append(r.get("conclusion"))

jobstats = collections.defaultdict(lambda: {"queue_min": [], "run_min": [], "conclusions": collections.Counter()})
failures = []
fetched = 0
for r in sorted(boot, key=lambda r: r["created_at"], reverse=True):
    if r.get("status") != "completed":
        continue
    want = r.get("conclusion") == "failure" or fetched < MAX_JOB_CALLS - 60
    if not want or fetched >= MAX_JOB_CALLS:
        continue
    fetched += 1
    jobs = api(f"repos/{REPO}/actions/runs/{r['id']}/jobs?per_page=50").get("jobs", [])
    failed_jobs = []
    for j in jobs:
        name = j.get("name")
        s, c, e = t(j.get("started_at")), t(j.get("created_at")), t(j.get("completed_at"))
        st = jobstats[name]
        st["conclusions"][j.get("conclusion")] += 1
        if s and c and e and j.get("conclusion") not in ("skipped", None):
            st["queue_min"].append(round((s - c).total_seconds() / 60, 1))
            st["run_min"].append(round((e - s).total_seconds() / 60, 1))
        if j.get("conclusion") == "failure":
            failed_step = next((x.get("name") for x in j.get("steps", []) if x.get("conclusion") == "failure"), None)
            failed_jobs.append({"job": name, "step": failed_step, "job_id": j.get("id")})
    if r.get("conclusion") == "failure":
        failures.append({
            "run_id": r["id"], "created": r["created_at"], "event": r["event"], "branch": r["head_branch"],
            "head_sha": r["head_sha"], "failed_jobs": failed_jobs,
            "linux_validate_same_sha": lin.get(r["head_sha"], []),
        })


def summary(xs):
    if not xs:
        return None
    xs = sorted(xs)
    return {"n": len(xs), "median": statistics.median(xs), "p90": xs[int(0.9 * (len(xs) - 1))], "max": xs[-1], "sum": round(sum(xs), 1)}


mac_only = [f for f in failures if any("macos" in (j["job"] or "") for j in f["failed_jobs"])
            and not any("macos" not in (j["job"] or "") for j in f["failed_jobs"])
            and "success" in f["linux_validate_same_sha"]]
out = {
    "since": SINCE, "api_calls": calls, "bootstrap_runs": len(boot), "validate_runs": len(val), "runs_with_jobs_fetched": fetched,
    "bootstrap_conclusions": dict(collections.Counter(r.get("conclusion") for r in boot)),
    "jobs": {k: {"queue": summary(v["queue_min"]), "run": summary(v["run_min"]), "conclusions": dict(v["conclusions"])} for k, v in jobstats.items()},
    "failures": failures,
    "macos_only_failures_linux_green": [f["run_id"] for f in mac_only],
}
p = pathlib.Path(__file__).with_name("macos-ci-evidence.json")
p.write_text(json.dumps(out, indent=1))
print(json.dumps({k: v for k, v in out.items() if k not in ("failures",)}, indent=1)[:4000])
print("failures:", len(failures), "macos-only with linux green:", len(mac_only), "->", p)
