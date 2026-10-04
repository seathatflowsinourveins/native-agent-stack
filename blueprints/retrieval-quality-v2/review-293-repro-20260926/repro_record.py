"""Re-run the review-293 reproductions against the ORIGINAL run.py and record sanitized observations."""
import datetime, hashlib, json, os, pathlib, shutil, sqlite3, subprocess, sys
G5 = pathlib.Path(__file__).resolve().parent
WT = G5.parent / "wt-g5"
PY = sys.executable
OUT = pathlib.Path(sys.argv[1])
BASE = G5 / "repro2"
shutil.rmtree(BASE, ignore_errors=True)
ORIG = BASE / "orig" / "blueprints" / "retrieval-quality-v2"
ORIG.mkdir(parents=True)
for name in ("run.py", "queries.json", "PREREGISTRATION.md", "results-20260925.json"):
    (ORIG / name).write_bytes(subprocess.run(["git", "-C", str(WT), "show", f"39e18ed5:blueprints/retrieval-quality-v2/{name}"],
                                             check=True, capture_output=True).stdout)
RUN = ORIG / "run.py"
STUB = G5 / "repro" / "stubqmd.py"
HOME = str(pathlib.Path.home())
def san(text):
    return str(text).replace(str(G5), "<SCRATCH>").replace(str(WT), "<STACK_REPO>").replace(HOME, "~")
queries = json.loads((WT / "blueprints/retrieval-quality-v2/queries.json").read_text())
sha = {d["path"]: d["sha256"] for d in queries["corpus"]}
PREFIX = {"blueprints/us-equities/": "rqv2-foundation", "catalogs/us-equities/": "rqv2-catalog", "observability/": "rqv2-observability"}
def uri(path):
    for p, c in PREFIX.items():
        if path.startswith(p):
            return f"qmd://{c}/{path[len(p):]}?index=retrieval-quality-v2"
def hit(path, docid=None):
    return {"docid": docid if docid is not None else "#" + sha[path][:6], "score": 0.9, "file": uri(path), "title": "t"}
def good(q):
    return json.dumps([hit(r["path"]) for r in sorted(q["relevance"], key=lambda r: -r["grade"])])
MODELS = ["hf:ggml-org/embeddinggemma-300M-GGUF/embeddinggemma-300M-Q8_0.gguf",
          "hf:tobil/qmd-query-expansion-1.7B-gguf/qmd-query-expansion-1.7B-q4_k_m.gguf",
          "hf:ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF/qwen3-reranker-0.6b-q8_0.gguf"]
def scenario(name, **over):
    d = BASE / name; d.mkdir(parents=True)
    sc = {"model_dir": str(d / "models"), "models": MODELS, "search": {"default": "[]"},
          "query": {"responses": {q["query"]: good(q) for q in queries["queries"]}}}
    for k, v in over.items():
        if k == "query":
            sc["query"]["responses"].update(v["responses"])
        elif isinstance(v, dict) and isinstance(sc.get(k), dict):
            sc[k] = {**sc[k], **v}
        else:
            sc[k] = v
    (d / "scenario.json").write_text(json.dumps(sc))
    return d
def run(d, *extra, env_extra=None, repo=WT, qmd=str(STUB)):
    env = dict(os.environ); env["STUB_SCENARIO"] = str(d / "scenario.json"); env.update(env_extra or {})
    argv = [PY, str(RUN), "--repo", str(repo), "--scratch-home", str(d / "home"), "--qmd-bin", qmd, *extra]
    p = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=900, cwd=str(BASE))
    return p, [san(a) for a in argv[1:]]
def receipt(date):
    return json.loads((ORIG / f"results-{date}.json").read_text())
record = {"schema_version": 1,
          "recorded_at_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
          "evidence_class": "local_integration",
          "subject": {"path": "blueprints/retrieval-quality-v2/run.py", "commit": "39e18ed568b9bd75d573dc92d2d47b95c8ae77a0",
                      "sha256": hashlib.sha256(RUN.read_bytes()).hexdigest()},
          "method": ("Each reproduction runs a copy of run.py as merged in #293, with its own copy of queries.json, "
                     "PREREGISTRATION.md and results-20260925.json as its output directory, so no tracked file is touched. F1 uses "
                     "the installed QMD 2.8.3 with decoy caller paths under the scratch directory standing in for host state; "
                     "F2-F6 use a stub qmd that emits the scripted responses. Hugging Face is made unreachable for F2 "
                     "with a dead HTTPS proxy. Paths are sanitized: <SCRATCH> is the worker scratch directory, "
                     "<STACK_REPO> the checkout."),
          "findings": []}
def add(fid, summary, argv, p, observed):
    record["findings"].append({"id": fid, "summary": summary, "argv": argv, "exit_code": p.returncode,
                               "stderr_tail": san(p.stderr.strip().splitlines()[-1]) if p.stderr.strip() else "",
                               "observed": observed})
# F1: real qmd, decoy caller routing
d = BASE / "f1"; decoy = d / "decoy"; (decoy / "config").mkdir(parents=True); (decoy / "notes").mkdir()
(decoy / "notes/a.md").write_text("# Host note A\nalpha\n"); (decoy / "notes/b.md").write_text("# Host note B\nbeta\n")
env0 = {"HOME": str(d / "h0"), "XDG_CACHE_HOME": str(d / "h0/.cache"), "XDG_CONFIG_HOME": str(d / "h0/.config"),
        "INDEX_PATH": str(decoy / "host.sqlite"), "QMD_CONFIG_DIR": str(decoy / "config"), "PATH": os.environ["PATH"],
        "MCP_AUTO_OPEN_ENABLED": "false"}
subprocess.run([shutil.which("qmd"), "--index", "hostidx", "collection", "add", str(decoy / "notes"), "--name", "host-notes", "--mask", "**/*.md"],
               env=env0, cwd=str(d), check=True, capture_output=True, timeout=120)
def decoy_state():
    con = sqlite3.connect(f"file:{decoy / 'host.sqlite'}?mode=ro", uri=True)
    try:
        rows = con.execute("SELECT collection, COUNT(*) FROM documents WHERE active = 1 GROUP BY collection ORDER BY collection").fetchall()
    finally:
        con.close()
    return {"db_bytes": (decoy / "host.sqlite").stat().st_size, "documents_by_collection": dict(rows),
            "config_files": sorted(p.name for p in (decoy / "config").iterdir())}
before = decoy_state()
p, argv = run(d, "--skip-arm-b", "--date", "f1", qmd=shutil.which("qmd"),
              env_extra={"INDEX_PATH": str(decoy / "host.sqlite"), "QMD_CONFIG_DIR": str(decoy / "config")})
r = receipt("f1")
add("F1", "Inherited INDEX_PATH/QMD_CONFIG_DIR route index and configuration writes to caller (host) storage",
    ["INDEX_PATH=<SCRATCH>/repro2/f1/decoy/host.sqlite", "QMD_CONFIG_DIR=<SCRATCH>/repro2/f1/decoy/config", *argv], p,
    {"status": r["status"], "abort_reason_head": san(r.get("abort_reason", ""))[:80],
     "decoy_before": before, "decoy_after": decoy_state(),
     "scratch_index_created": (d / "home/.cache/qmd/retrieval-quality-v2.sqlite").exists()})
# F2: HF unreachable
d = scenario("f2")
p, argv = run(d, "--date", "f2", env_extra={"https_proxy": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9"})
r = receipt("f2")
add("F2", "Unresolved HF revisions do not stop Arm B", ["HTTPS_PROXY=http://127.0.0.1:9", *argv], p,
    {"status": r["status"], "arm_b_status": r["arm_b"]["status"], "decision": r["decision"]["decision"],
     "revisions": {m["role"]: m["hf_repo_revision"] for m in r["arm_b"]["model_provenance"]["models"]},
     "revision_errors": {m["role"]: (m["hf_repo_revision_error"] or "")[:40] for m in r["arm_b"]["model_provenance"]["models"]}})
# F3: wrong and empty docid
q1, q2 = queries["queries"][0], queries["queries"][1]
g1 = [x["path"] for x in q1["relevance"] if x["grade"] == 2][0]; g2 = [x["path"] for x in q2["relevance"] if x["grade"] == 2][0]
d = scenario("f3", query={"responses": {q1["query"]: json.dumps([hit(g1, "#000000")]), q2["query"]: json.dumps([hit(g2, "")])}})
p, argv = run(d, "--date", "f3")
r = receipt("f3")
add("F3", "Hits with a wrong or empty docid are still credited", argv, p,
    {"status": r["status"], "per_query": [{k: e[k] for k in ("id", "ndcg_at_10", "error", "resolution_notes")} for e in r["arm_b"]["per_query"][:2]],
     "scripted_docids": {q1["id"]: "#000000", q2["id"]: ""}})
# F4: wrong-shaped JSON
for tag, shape in (("F4a", "{}"), ("F4b", "[42]"), ("F4c", "null")):
    d = scenario(tag.lower(), search={"responses": {q1["query"]: shape}})
    p, argv = run(d, "--skip-arm-b", "--date", tag.lower())
    r = receipt(tag.lower())
    first = r["arm_a"]["per_query"][0] if r["arm_a"]["per_query"] else None
    add(tag, f"Arm A response {shape} for {q1['id']}", argv, p,
        {"status": r["status"], "abort_reason": san(r["abort_reason"]) if r.get("abort_reason") else None,
         "first_query": {k: first[k] for k in ("id", "error", "ndcg_at_10")} if first else None})
# F5: setup timeouts
for tag, step in (("F5a", "pull"), ("F5b", "embed")):
    d = scenario(tag.lower(), **{step: {"sleep": 5}})
    p, argv = run(d, "--date", tag.lower(), f"--{step}-timeout", "1")
    r = receipt(tag.lower())
    add(tag, f"`qmd {step}` timing out", argv, p,
        {"status": r["status"], "decision": r["decision"], "abort_reason_head": san(r.get("abort_reason", ""))[:60]})
# F6: overwrite of the historical receipt
target = ORIG / "results-20260925.json"
before_sha = hashlib.sha256(target.read_bytes()).hexdigest()
fake = BASE / "f6-repo" / "blueprints/retrieval-quality-v2"; fake.mkdir(parents=True)
shutil.copy(ORIG / "PREREGISTRATION.md", fake / "PREREGISTRATION.md"); (fake / "queries.json").write_text("{}")
d = scenario("f6")
p, argv = run(d, repo=BASE / "f6-repo")
add("F6", "A run whose seal check fails still writes results-20260925.json", argv, p,
    {"results_20260925_sha256_before": before_sha, "results_20260925_sha256_after": hashlib.sha256(target.read_bytes()).hexdigest(),
     "status_now_in_that_file": json.loads(target.read_text())["status"]})
# F7: what a successful run retains
r = json.loads(subprocess.run(["git", "-C", str(WT), "show", "39e18ed5:blueprints/retrieval-quality-v2/results-20260925.json"],
                              check=True, capture_output=True).stdout)
record["findings"].append({"id": "F7", "summary": "Successful retrieval stdout/stderr is not retained",
                           "argv": None, "exit_code": None, "stderr_tail": "",
                           "observed": {"per_query_fields": sorted(r["arm_b"]["per_query"][0].keys()),
                                        "strong_bm25_signal_mentions_in_results_20260925": json.dumps(r).count("Strong BM25 signal")}})
mutations = G5 / "mut" / "mutation-summary.json"
if mutations.exists():
    record["discriminating_controls"] = json.loads(mutations.read_text())
text = json.dumps(record, indent=2) + "\n"
assert HOME not in text and "/home/" not in text and "<user>" not in text
with open(OUT, "x") as fh:
    fh.write(text)
print(text)
