#!/usr/bin/env python3
"""Preregistered battery for the catalog automation comparison. Usage: battery_catalog.py <arm-dir> <out.json>"""
import json, re, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import wfemu

ARM = Path(sys.argv[1]).resolve(); OUT = sys.argv[2]
HERE = Path(__file__).parent
SETTINGS = HERE.parent / "gh-settings" / "after"
ACTIONLINT = HERE.parent / "actionlint_dir" / "actionlint"
WF = ARM / ".github/workflows"
checks = []

def check(cid, fn):
    try:
        ok, detail = fn()
        checks.append({"id": cid, "applicable": ok is not None, "pass": bool(ok), "detail": detail})
    except Exception as exc:
        checks.append({"id": cid, "applicable": False, "pass": False, "detail": f"harness_error: {type(exc).__name__}: {exc}"[:400]})

def sec_wf():
    cands = [p for p in WF.glob("*.y*ml") if wfemu.jobs_with(p, "osv-scanner")]
    if not cands:
        raise RuntimeError("no workflow runs osv-scanner")
    return cands[0]

def osv_case(rc):
    wf = sec_wf(); jobs = wfemu.jobs_with(wf, "osv-scanner")
    rep = wfemu.run_workflow(wf, ARM, event="push", env_extra={"FAKE_OSV_SCANNER_RC": str(rc)}, only_jobs=jobs)
    failed = any(rep["jobs"][j]["result"] == "failure" for j in jobs if j in rep["jobs"])
    ups = [u for u in rep["uploads"] if "osv" in (u["category"] + u["file"]).lower()]
    return failed, ups, rep

def b1():
    failed, ups, rep = osv_case(1)
    ok = failed and any(u["valid"] for u in ups)
    return ok, {"job_failed": failed, "uploads": ups, "steps": {j: v["steps"] for j, v in rep["jobs"].items()}}
def b2():
    failed, ups, rep = osv_case(0)
    return (not failed) and any(u["valid"] for u in ups), {"job_failed": failed, "uploads": ups}
def b3():
    failed, ups, rep = osv_case(2)
    return failed, {"job_failed": failed}

def zizmor_case(rc):
    wf = sec_wf(); jobs = wfemu.jobs_with(wf, "zizmor")
    if not jobs:
        return None, None
    rep = wfemu.run_workflow(wf, ARM, event="push", env_extra={"FAKE_ZIZMOR_RC": str(rc)}, only_jobs=jobs)
    ups = [u for u in rep["uploads"] if "zizmor" in (u["category"] + u["file"]).lower()]
    return ups, rep

def b5():  # crash: no upload of an empty/invalid SARIF
    ups, rep = zizmor_case(3)
    if ups is None:
        return None, "no online analyzer job"
    return all(u["valid"] for u in ups), {"uploads_run": ups, "jobs": {j: v["result"] for j, v in rep["jobs"].items()}}
def b5b():  # normal: SARIF uploaded
    ups, rep = zizmor_case(0)
    if ups is None:
        return None, "no online analyzer job"
    return any(u["valid"] for u in ups), {"uploads_run": ups}

def b4():  # no run step in a code-scanning-write job receives a token
    bad = []
    for p in WF.glob("*.y*ml"):
        wf = wfemu.load(p)
        for j, s in wf.get("jobs", {}).items():
            pm = wfemu.perms(s)
            if pm.get("security-events") == "write" or pm.get("*") == "write-all":
                for st in s.get("steps", []):
                    if "run" in st:
                        blob = json.dumps(st.get("env") or {}) + st["run"]
                        if re.search(r"github\.token|GITHUB_TOKEN|GH_TOKEN", blob):
                            bad.append(f"{p.name}:{j}:{st.get('name', '')}")
    return not bad, {"token_exposed_steps": bad}

def b6():
    bad = []
    for p in WF.glob("*.y*ml"):
        for m in re.finditer(r"uses:\s*([^\s#]+)", p.read_text(encoding="utf-8")):
            u = m.group(1)
            if u.startswith("./") or u.startswith("docker://"):
                continue
            if not re.search(r"@[0-9a-f]{40}$", u):
                bad.append(f"{p.name}:{u}")
    return not bad, {"unpinned": bad}

LOCK = r"(^|/)(requirements[^/]*\.txt|[^/]*\.lock(\.txt)?|uv\.lock|pnpm-lock\.yaml|package-lock\.json|packages\.lock\.json|poetry\.lock|Pipfile\.lock)$"
def b7():
    files = wfemu.tracked(ARM, LOCK)
    blob = "".join(q.read_text(encoding="utf-8", errors="ignore") for q in (ARM / ".github").rglob("*") if q.is_file())
    handled = [f for f in files if f in blob]
    missing = sorted(set(files) - set(handled))
    frac = round(len(handled) / len(files), 4) if files else None
    return (not missing) if files else None, {"tracked": len(files), "handled": len(handled), "fraction": frac, "missing": missing[:40]}

def b9():
    p = WF / "publish-catalog.yml"; wf = wfemu.load(p)
    rel = [j for j, s in wf["jobs"].items() if any("gh release" in str(st.get("run", "")) for st in s.get("steps", []))]
    if not rel:
        return False, "no release job"
    j = rel[0]; s = wf["jobs"][j]; text = json.dumps(s)
    tag_only = "refs/tags/" in str(s.get("if", "")) or "refs/tags/" in text[:400]
    scoped = wfemu.perms(s).get("contents") == "write" and all(wfemu.perms(o).get("contents") != "write" for k, o in wf["jobs"].items() if k != j) and wfemu.perms({"permissions": wf.get("permissions")}).get("contents") != "write"
    runs = " ".join(str(st.get("run", "")) for st in s.get("steps", []))
    attach = bool(re.search(r"gh release create[^\n]*(\.tar\.gz|\$\w+|\")", runs)) or ("--draft" in runs and "gh release upload" in runs)
    digest = bool(re.search(r"sha256|digest", runs))
    return tag_only and scoped and attach and digest, {"job": j, "tag_only": tag_only, "contents_write_only_here": scoped, "assets_at_creation": attach, "digest_check": digest}

def b10():
    t = (WF / "dependency-review.yml").read_text(encoding="utf-8")
    return bool(re.search(r"fail-on-severity:\s*(high|critical)", t)) and not re.search(r"warn-only:\s*true", t), {}

def b11():
    p = WF / "supply-chain.yml"; t = p.read_text(encoding="utf-8"); on = wfemu.load(p)["on"]
    paths = {e: (on.get(e) or {}).get("paths", []) for e in ("push", "pull_request")}
    ok = bool(re.search(r"--fail-on\s+(high|critical)", t)) and all(".grype.yaml" in v for v in paths.values())
    return ok, {"paths_include_grype_yaml": {e: ".grype.yaml" in v for e, v in paths.items()}}

def b12():
    r = json.loads((ARM / ".github/main-ruleset.json").read_text(encoding="utf-8"))
    types = [x["type"] for x in r["rules"]]
    rsc = next(x for x in r["rules"] if x["type"] == "required_status_checks")["parameters"]
    ctx = [c["context"] for c in rsc["required_status_checks"]]
    cs = [x for x in r["rules"] if x["type"] == "code_scanning"]
    tools = [t.get("tool") for x in cs for t in x.get("parameters", {}).get("code_scanning_tools", [])]
    ok = "required_signatures" not in types and rsc.get("strict_required_status_checks_policy") is False and "dependency-review" in ctx and any("osv" in c for c in ctx) and "CodeQL" in tools
    return ok, {"rules": types, "strict": rsc.get("strict_required_status_checks_policy"), "contexts": ctx, "code_scanning_tools": tools}

def b13():
    def norm(d):
        return {"rules": sorted(x["type"] for x in d.get("rules", [])), "bypass": sorted((b.get("actor_type"), b.get("actor_id"), b.get("bypass_mode")) for b in d.get("bypass_actors", []))}
    live = [norm(json.loads((SETTINGS / n).read_text())) for n in ("native-agent-stack-ruleset-tag.json", "native-agent-stack-ruleset-tag-creation.json")]
    files = [norm(json.loads(q.read_text())) for q in (ARM / ".github").glob("*ruleset*.json") if json.loads(q.read_text()).get("target") == "tag"]
    return all(l in files for l in live), {"live": live, "committed_tag_rulesets": files}

check("B1_osv_findings_still_upload_sarif_and_fail", b1)
check("B2_osv_clean_uploads_sarif_and_passes", b2)
check("B3_osv_scanner_error_fails", b3)
check("B4_no_token_in_code_scanning_write_run_steps", b4)
check("B5_analyzer_crash_never_uploads_invalid_sarif", b5)
check("B5b_analyzer_findings_upload_valid_sarif", b5b)
check("B6_all_actions_sha_pinned", b6)
check("B7_every_tracked_lockfile_handled", b7)
check("B9_release_job_tag_only_scoped_assets_digest", b9)
check("B10_dependency_review_gates_high", b10)
check("B11_grype_gate_and_policy_path_filter", b11)
check("B12_target_ruleset_decisions", b12)
check("B13_tag_ruleset_files_equal_live", b13)

own = []
cmds = [["python3", "scripts/validate.py"], ["python3", "scripts/evidence_manifest.py", "--check"], ["python3", "tools/sota-convergence/build_verdicts.py", "--check"],
        ["python3", "scripts/component_matrix.py", "--check"], ["python3", "scripts/build_ecosystem.py", "--check"],
        ["python3", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"], [str(ACTIONLINT), "-color=false"],
        ["zizmor", "--offline", "--no-config", "--no-ignores", "--persona", "regular", "--strict-collection", ".github/workflows"]]
for c in cmds:
    if c[0] == "python3" and not (ARM / c[1]).exists() and c[1] != "-m":
        own.append({"cmd": " ".join(c), "rc": None, "note": "absent"}); continue
    p = subprocess.run(c, cwd=ARM, capture_output=True, text=True, timeout=900)
    own.append({"cmd": " ".join(c), "rc": p.returncode, "tail": (p.stdout + p.stderr).strip()[-240:]})
app = [c for c in checks if c["applicable"]]
res = {"arm_dir_label": ARM.name, "checks": checks, "battery_pass_rate": round(sum(c["pass"] for c in app) / len(app), 4) if app else None,
       "applicable": len(app), "passed": sum(c["pass"] for c in app), "own_suite": own,
       "own_suite_pass": int(all(o["rc"] == 0 for o in own if o["rc"] is not None))}
Path(OUT).write_text(json.dumps(res, indent=1))
print(json.dumps({"label": ARM.name, "battery_pass_rate": res["battery_pass_rate"], "passed": res["passed"], "applicable": res["applicable"], "own_suite_pass": res["own_suite_pass"]}))
