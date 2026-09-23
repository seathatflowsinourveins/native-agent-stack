import json, subprocess, sys, datetime

repos = [
    "OpenHands/software-agent-sdk",
    "andrewyng/context-hub",
    "dagucloud/dagu",
    "headroomlabs-ai/headroom",
    "Arize-ai/phoenix",
    "UKGovernmentBEIS/inspect_ai",
    "tobi/qmd",
    "tsdgeos/poppler_mirror",
    "microsoft/markitdown",
    "max-sixty/worktrunk",
    "gastownhall/beads",
    "gitleaks/gitleaks",
    "anchore/syft",
    "anchore/grype",
]

out = {}
for repo in repos:
    entry = {}
    try:
        r = subprocess.run(["gh","api",f"repos/{repo}","--jq",
            '{full_name:.full_name, default_branch:.default_branch, pushed_at:.pushed_at, archived:.archived, disabled:.disabled}'],
            capture_output=True, text=True, timeout=30)
        entry["repo"] = json.loads(r.stdout) if r.returncode==0 and r.stdout.strip() else None
        entry["repo_exit"] = r.returncode
        entry["repo_stderr"] = r.stderr.strip()
    except Exception as e:
        entry["repo_error"] = str(e)
    try:
        r2 = subprocess.run(["gh","api",f"repos/{repo}/releases/latest","--jq",
            '{tag_name:.tag_name, published_at:.published_at, target_commitish:.target_commitish}'],
            capture_output=True, text=True, timeout=30)
        entry["latest_release"] = json.loads(r2.stdout) if r2.returncode==0 and r2.stdout.strip() else None
        entry["latest_release_exit"] = r2.returncode
        entry["latest_release_stderr"] = r2.stderr.strip()
    except Exception as e:
        entry["latest_release_error"] = str(e)
    try:
        r3 = subprocess.run(["gh","api",f"repos/{repo}/commits/HEAD","--jq",
            '{sha:.sha, date:.commit.committer.date}'],
            capture_output=True, text=True, timeout=30)
        entry["head_commit"] = json.loads(r3.stdout) if r3.returncode==0 and r3.stdout.strip() else None
        entry["head_commit_exit"] = r3.returncode
        entry["head_commit_stderr"] = r3.stderr.strip()
    except Exception as e:
        entry["head_commit_error"] = str(e)
    out[repo] = entry
    print(repo, "->", entry.get("repo_exit"), entry.get("latest_release_exit"), entry.get("head_commit_exit"), file=sys.stderr)

out["_swept_at_utc"] = datetime.datetime.utcnow().isoformat()+"Z"
json.dump(out, sys.stdout, indent=2)
