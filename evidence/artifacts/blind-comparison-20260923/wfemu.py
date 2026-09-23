"""Minimal GitHub Actions job emulator for battery checks (shared by both batteries).

Runs a workflow's jobs for one event with fake tool binaries: `uses:` steps are modelled
(upload-sarif validates its file, upload/download-artifact move files, others succeed),
`run:` steps execute under GitHub's shell semantics, `if:` expressions and job `needs`
are evaluated for the subset of expressions these workflows use. Install steps (curl
download + checksum, pip install) are skipped because fakes are pre-placed.
"""
import json, os, re, shutil, subprocess, tempfile
from pathlib import Path
import yaml

FAKE = r'''#!/usr/bin/env bash
# fake __NAME__: honours FAKE___UP___RC; writes SARIF for --format sarif (to --output/--output-file or stdout)
name=__NAME__; rc_var=FAKE___UP___RC; rc=${!rc_var:-0}
for a in "$@"; do [ "$a" = "--version" ] && { echo "$name version 0.0.0-fake"; exit 0; }; done
fmt=""; out=""; prev=""
for a in "$@"; do
  case "$prev" in --format) fmt="$a";; --output|--output-file) out="$a";; esac
  case "$a" in --format=*) fmt="${a#--format=}";; --output=*|--output-file=*) out="${a#*=}";; esac
  prev="$a"
done
if [ "$rc" -ge 3 ] && [ "$name" = zizmor ]; then echo "fake crash" >&2; exit "$rc"; fi
if [ "$rc" -ge 2 ] && [ "$name" = osv-scanner ]; then echo "fake scanner error" >&2; exit "$rc"; fi
if [ "$fmt" = sarif ]; then
  s='{"version":"2.1.0","$schema":"https://json.schemastore.org/sarif-2.1.0.json","runs":[{"tool":{"driver":{"name":"fake"}},"results":[]}]}'
  if [ -n "$out" ]; then printf '%s' "$s" > "$out"; else printf '%s' "$s"; fi
else
  echo "fake $name table output (rc=$rc)"
fi
exit "$rc"
'''

def load(path):
    d = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if True in d and "on" not in d:
        d["on"] = d.pop(True)
    return d

def expr_value(e, ctx):
    e = e.strip()
    m = re.fullmatch(r"steps\.([\w-]+)\.outcome\s*==\s*'(\w+)'", e)
    if m:
        return "true" if ctx["outcomes"].get(m.group(1)) == m.group(2) else "false"
    simple = {"github.token": "fake-token", "secrets.GITHUB_TOKEN": "fake-token", "runner.temp": ctx["temp"],
              "github.run_id": "1", "github.workspace": ctx["cwd"], "github.event_name": ctx["event"],
              "github.ref": ctx.get("ref", "refs/heads/main"), "github.repository": "owner/repo", "github.sha": "0" * 40}
    if e in simple:
        return simple[e]
    if re.search(r"github\.event_name\s*[!=]=", e) or "cancelled()" in e or "success()" in e:
        return "true" if eval_cond(e, ctx) else "false"
    return ""

def interpolate(text, ctx):
    return re.sub(r"\$\{\{(.*?)\}\}", lambda m: expr_value(m.group(1), ctx), str(text))

def eval_cond(cond, ctx):
    if cond is None:
        return not ctx["failed"]
    c = str(cond).strip()
    if c.startswith("${{") and c.endswith("}}"):
        c = c[3:-2]
    status_fn = any(f in c for f in ("always()", "cancelled()", "failure()", "success()"))
    py = c
    py = re.sub(r"github\.event_name\s*!=\s*'([\w-]+)'", lambda m: str(ctx["event"] != m.group(1)), py)
    py = re.sub(r"github\.event_name\s*==\s*'([\w-]+)'", lambda m: str(ctx["event"] == m.group(1)), py)
    py = re.sub(r"startsWith\(\s*github\.ref\s*,\s*'([^']*)'\s*\)", lambda m: str(ctx.get("ref", "").startswith(m.group(1))), py)
    py = re.sub(r"github\.ref\s*==\s*'([^']*)'", lambda m: str(ctx.get("ref", "") == m.group(1)), py)
    py = re.sub(r"github\.repository\s*==\s*'([^']*)'", "True", py)
    py = re.sub(r"steps\.([\w-]+)\.outcome\s*==\s*'(\w+)'", lambda m: str(ctx["outcomes"].get(m.group(1)) == m.group(2)), py)
    py = re.sub(r"needs\.([\w-]+)\.outputs\.([\w-]+)\s*==\s*'(\w+)'", lambda m: str(str(ctx["needs_outputs"].get(m.group(1), {}).get(m.group(2), "")) == m.group(3)), py)
    py = re.sub(r"needs\.([\w-]+)\.result\s*==\s*'(\w+)'", lambda m: str(ctx["needs_results"].get(m.group(1)) == m.group(2)), py)
    py = py.replace("always()", "True").replace("!cancelled()", "True").replace("cancelled()", "False")
    py = py.replace("failure()", str(ctx["failed"])).replace("success()", str(not ctx["failed"]))
    py = py.replace("&&", " and ").replace("||", " or ")
    py = re.sub(r"!(?!=)", " not ", py)
    try:
        val = bool(eval(py, {"__builtins__": {}}, {"True": True, "False": False}))
    except Exception as exc:
        raise RuntimeError(f"unsupported if: {cond!r} -> {py!r}: {exc}")
    if not status_fn and ctx["failed"]:
        return False
    return val

def is_install(run):
    return ("curl" in run and "sha256sum" in run) or re.search(r"pip install", run) is not None

def valid_sarif(p):
    try:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        return isinstance(d, dict) and d.get("version") == "2.1.0" and isinstance(d.get("runs"), list)
    except Exception:
        return False

def place_fakes(workflow_text, temp, bindir, names):
    for name in names:
        body = FAKE.replace("__NAME__", name).replace("__UP__", name.upper().replace("-", "_"))
        for dest in [Path(bindir) / name]:
            dest.write_text(body); dest.chmod(0o755)
        # binaries referenced as "$RUNNER_TEMP/<dir>/<name>" (not the directory itself)
        for m in re.finditer(r"\$\{?RUNNER_TEMP\}?/((?:[\w.-]+/)+)" + re.escape(name) + r"(?![\w.-])", workflow_text):
            d = Path(temp) / m.group(1); d.mkdir(parents=True, exist_ok=True)
            f = d / name
            if not f.exists():
                f.write_text(body); f.chmod(0o755)

def run_workflow(wf_path, cwd, event="push", env_extra=None, only_jobs=None, fakes=("osv-scanner", "zizmor"), ref="refs/heads/main"):
    wf = load(wf_path); text = Path(wf_path).read_text(encoding="utf-8")
    temp = tempfile.mkdtemp(prefix="emu-temp-"); bindir = tempfile.mkdtemp(prefix="emu-bin-")
    place_fakes(text, temp, bindir, fakes)
    artifacts = {}; jobs = wf.get("jobs", {}); results = {}; outputs = {}; report = {"jobs": {}, "uploads": []}
    order = list(jobs)
    if only_jobs:
        keep = set(only_jobs)
        changed = True
        while changed:
            changed = False
            for j, spec in jobs.items():
                needs = spec.get("needs", []) or []
                needs = [needs] if isinstance(needs, str) else needs
                if j not in keep and any(n in keep for n in needs):
                    keep.add(j); changed = True
        order = [j for j in order if j in keep]
    pending = list(order)
    while pending:
        progressed = False
        for j in list(pending):
            spec = jobs[j]; needs = spec.get("needs", []) or []; needs = [needs] if isinstance(needs, str) else needs
            if any(n in pending for n in needs):
                continue
            pending.remove(j); progressed = True
            ctx = {"failed": any(results.get(n) != "success" for n in needs if n in results), "outcomes": {}, "event": event,
                   "temp": temp, "cwd": str(cwd), "needs_results": results, "needs_outputs": outputs, "ref": ref}
            jc = spec.get("if")
            run_job = eval_cond(jc, ctx) if jc is not None else not ctx["failed"]
            if not run_job:
                results[j] = "skipped"; report["jobs"][j] = {"result": "skipped", "steps": []}; continue
            ctx["failed"] = False
            env = {**(wf.get("env") or {}), **(spec.get("env") or {})}
            steps_log = []
            for i, st in enumerate(spec.get("steps", [])):
                sid = st.get("id", f"step{i}")
                if not eval_cond(st.get("if"), ctx):
                    ctx["outcomes"][sid] = "skipped"; steps_log.append((sid, "skipped", None)); continue
                if "uses" in st:
                    u = st["uses"]; w = {k: interpolate(v, ctx) for k, v in (st.get("with") or {}).items()}
                    outcome = "success"; extra = None
                    if "upload-sarif" in u:
                        p = w.get("sarif_file", ""); ok = valid_sarif(p)
                        report["uploads"].append({"job": j, "step": sid, "category": w.get("category", ""), "file": p, "valid": ok})
                        outcome = "success" if ok else "failure"; extra = "valid" if ok else "invalid-or-missing"
                    elif "upload-artifact" in u:
                        p = w.get("path", ""); name = w.get("name", "artifact")
                        if Path(p).exists():
                            artifacts[name] = p
                        elif str(w.get("if-no-files-found", "warn")) == "error":
                            outcome = "failure"
                    elif "download-artifact" in u:
                        name = w.get("name", ""); dest = Path(w.get("path", temp)); src = artifacts.get(name)
                        if src and Path(src).exists():
                            dest.mkdir(parents=True, exist_ok=True)
                            if Path(src).resolve() != (dest / Path(src).name).resolve():
                                shutil.copy(src, dest / Path(src).name)
                        else:
                            outcome = "failure"
                    ctx["outcomes"][sid] = outcome; ctx["failed"] |= outcome == "failure"; steps_log.append((sid, outcome, extra)); continue
                run = st.get("run", "")
                if is_install(run):
                    ctx["outcomes"][sid] = "success"; steps_log.append((sid, "success", "install-skipped")); continue
                senv = {k: interpolate(v, ctx) for k, v in {**env, **(st.get("env") or {})}.items()}
                script = interpolate(run, ctx)
                shell = st.get("shell", spec.get("defaults", {}).get("run", {}).get("shell") if isinstance(spec.get("defaults"), dict) else None)
                argv = ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", script] if shell == "bash" else ["bash", "-e", "-c", script]
                penv = {**os.environ, **{k: str(v) for k, v in senv.items()}, "RUNNER_TEMP": temp, "PATH": bindir + ":" + os.environ["PATH"], **(env_extra or {})}
                p = subprocess.run(argv, cwd=cwd, env=penv, capture_output=True, text=True, timeout=600)
                outcome = "success" if p.returncode == 0 else "failure"
                ctx["outcomes"][sid] = outcome; ctx["failed"] |= outcome == "failure"
                steps_log.append((sid, outcome, f"rc={p.returncode} {p.stderr.strip()[-160:]}"))
            results[j] = "failure" if ctx["failed"] else "success"
            outputs[j] = {k: interpolate(v, ctx) for k, v in (spec.get("outputs") or {}).items()}
            report["jobs"][j] = {"result": results[j], "steps": steps_log, "outputs": outputs[j]}
        if not progressed:
            raise RuntimeError(f"unresolvable needs among {pending}")
    shutil.rmtree(bindir, ignore_errors=True); shutil.rmtree(temp, ignore_errors=True)
    return report

def jobs_with(wf_path, needle):
    wf = load(wf_path)
    return [j for j, s in wf.get("jobs", {}).items() if any(needle in str(st.get("run", "")) + str(st.get("uses", "")) for st in s.get("steps", []))]

def perms(spec):
    p = spec.get("permissions")
    if isinstance(p, str):
        return {"*": p}
    return p or {}

def tracked(cwd, patterns):
    out = subprocess.run(["git", "ls-files"], cwd=cwd, capture_output=True, text=True).stdout.split()
    rx = re.compile(patterns)
    return [f for f in out if rx.search(f) and "node_modules/" not in f]
