"""Offline regression tests for blueprints/retrieval-quality-v2/run.py.

The runner is driven end to end against a synthetic four-file corpus in a
scratch git repository and a stub standing in for the qmd CLI. No test
starts the real qmd, loads a model or reaches Hugging Face; every output
goes to a temporary directory, never next to run.py. These tests cover the
harness's own contracts (environment isolation, fail-closed model pinning,
response validation, timeouts, stopping on SIGINT, SIGTERM and SIGHUP,
unique outputs, native-output retention and sanitization, and the ``qmd
bench`` audit and its refusal of incomplete output); they are not evidence
about QMD's behaviour. The signal tests run the runner in a child process
and signal only that process, or let the stub or the child signal itself.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from tests import hermetic_git_environment

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("retrieval_quality_v2_run", ROOT / "blueprints/retrieval-quality-v2/run.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)

RUN_ID = "20260926T000000Z"
CORPUS = {
    "blueprints/us-equities/README.md": "# Root blueprint\nplanning overview\n",
    "blueprints/us-equities/data/README.md": "# Data\nvolume parsing and decimal checks\n",
    "catalogs/us-equities/notes.md": "# Catalog notes\nlicensing and vendor notes\n",
    "observability/README.md": "# Observability\ncollector restart guide\n",
}
QUERIES = [
    ("kw-01", "keyword", "volume decimal parsing",
     [("blueprints/us-equities/data/README.md", 2), ("blueprints/us-equities/README.md", 1)]),
    ("nl-01", "natural_language", "Which vendor licensing notes apply?", [("catalogs/us-equities/notes.md", 2)]),
    ("pa-01", "paraphrased_indirect", "bringing the telemetry agent back up", [("observability/README.md", 2)]),
    ("kw-02", "keyword", "planning overview", [("blueprints/us-equities/README.md", 2)]),
]
MODELS = [
    "hf:ggml-org/embeddinggemma-300M-GGUF/embeddinggemma-300M-Q8_0.gguf",
    "hf:tobil/qmd-query-expansion-1.7B-gguf/qmd-query-expansion-1.7B-q4_k_m.gguf",
    "hf:ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF/qwen3-reranker-0.6b-q8_0.gguf",
]
SHA = {path: hashlib.sha256(text.encode()).hexdigest() for path, text in CORPUS.items()}

# The stub imitates only the qmd CLI surface run.py uses: it records every
# call's argv, cwd and selected environment, keeps a tiny SQLite index with
# QMD's `documents`/`llm_cache` columns at $INDEX_PATH, and answers
# search/query/bench from the baked-in scenario.
STUB = r'''
import hashlib, json, os, pathlib, signal, sqlite3, subprocess, sys, time
SCENARIO = json.loads(pathlib.Path(__file__).with_name("scenario.json").read_text())
argv = sys.argv[1:]
with open(SCENARIO["log"], "a") as fh:
    fh.write(json.dumps({"argv": argv, "cwd": os.getcwd(), "env": dict(os.environ)}) + "\n")
index = None
if "--index" in argv:
    at = argv.index("--index")
    index = argv[at + 1]
    del argv[at:at + 2]
if argv == ["--version"]:
    print(SCENARIO.get("version", "qmd 2.8.3 (stub)"))
    sys.exit(0)
def hang_here(hang):
    # Stand-in for a slow qmd call: optionally a grandchild in the same process group
    # and partial output, then a marker the test waits for before it signals the runner.
    pids = {"stub": os.getpid()}
    if hang.get("sleeper"):
        pids["sleeper"] = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"]).pid
    if hang.get("partial"):
        sys.stdout.write("[partial stdout before the hang")
        sys.stderr.write("Expanding query before the hang\n")
        sys.stdout.flush()
        sys.stderr.flush()
    marker = pathlib.Path(hang["marker"])
    marker.with_suffix(".tmp").write_text(json.dumps(pids))
    marker.with_suffix(".tmp").replace(marker)
    time.sleep(hang.get("seconds", 120))
cmd = argv[0]
behaviour = SCENARIO.get(cmd, {})
if behaviour.get("spawn_sleeper"):
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    pathlib.Path(behaviour["spawn_sleeper"]).write_text(str(child.pid))
if behaviour.get("sleep"):
    time.sleep(behaviour["sleep"])
db = pathlib.Path(os.environ["INDEX_PATH"])
def connect():
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE IF NOT EXISTS documents (collection TEXT, path TEXT, hash TEXT, active INTEGER)")
    conn.execute("CREATE TABLE IF NOT EXISTS llm_cache (hash TEXT)")
    return conn
if cmd == "collection":
    root = pathlib.Path(argv[2])
    name = argv[argv.index("--name") + 1]
    conn = connect()
    for f in sorted(root.rglob("*.md")):
        rel = f.relative_to(root).as_posix()
        digest = SCENARIO.get("hash_override", {}).get(rel, hashlib.sha256(f.read_bytes()).hexdigest())
        conn.execute("INSERT INTO documents VALUES (?, ?, ?, 1)", (name, rel, digest))
    conn.commit()
    conn.close()
    config = pathlib.Path(os.environ["QMD_CONFIG_DIR"]) / f"{index}.yml"
    config.parent.mkdir(parents=True, exist_ok=True)
    with open(config, "a") as fh:
        fh.write(f"{name}: {root}\n")
    print(f"Collection '{name}' created")
    sys.exit(0)
if cmd == "update":
    sys.exit(0)
if cmd == "status":
    conn = connect()
    total = conn.execute("SELECT COUNT(*) FROM documents WHERE active = 1").fetchone()[0]
    print(f"QMD Status\n\nDocuments\n  Total:    {total} files indexed\n")
    sys.exit(0)
if cmd == "pull":
    models = pathlib.Path(os.environ["XDG_CACHE_HOME"]) / "qmd" / "models"
    models.mkdir(parents=True, exist_ok=True)
    for uri in SCENARIO["models"]:
        org, _repo, filename = uri[len("hf:"):].split("/", 2)
        # QMD 2.8.3's layout: node-llama-cpp saves the download as hf_<org>_<file>, and
        # pullModels caches the file's ETag as <file>.etag (dist/llm.js).
        target = models / f"hf_{org}_{filename}"
        target.write_bytes(uri.encode())
        (models / f"{filename}.etag").write_text('"' + hashlib.sha256(b"xet:" + uri.encode()).hexdigest() + '"\n')
        print(f"- {uri} -> {target} (1 KB, {SCENARIO.get('pull_note', 'refreshed')})")
    sys.exit(0)
if cmd == "embed":
    conn = connect()
    total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    print(f"Done! Embedded {total} chunks from {total} documents in 1s")
    sys.exit(0)
if cmd in ("search", "query"):
    hang = behaviour.get("hang", {}).get(argv[1])
    if hang:
        hang_here(hang)
    sys.stderr.write(behaviour.get("stderr", {}).get(argv[1], ""))
    sys.stdout.write(behaviour.get("responses", {}).get(argv[1], behaviour.get("default", "[]")))
    sys.stdout.flush()
    # A signal to the runner (this process's parent) while this call runs; the call then ends
    # at once, before the runner's next poll for a stop.
    parent_signal = behaviour.get("signal_parent", {}).get(argv[1])
    if parent_signal:
        os.kill(os.getppid(), getattr(signal, parent_signal))
    sys.exit(0)
if cmd == "bench":
    if behaviour.get("hang"):
        hang_here(behaviour["hang"])
    sys.stdout.write(behaviour.get("stdout", "{}"))
    sys.exit(behaviour.get("exit", 0))
sys.exit(3)
'''


def virtual(path):
    return M.virtual_path(path)


def hit(path, docid=None):
    return {"docid": "#" + SHA[path][:6] if docid is None else docid, "score": 0.9,
            "file": virtual(path) + "?index=retrieval-quality-v2", "title": "t"}


def perfect(query_id):
    relevance = next(q[3] for q in QUERIES if q[0] == query_id)
    return json.dumps([hit(path) for path, _grade in sorted(relevance, key=lambda r: -r[1])])


def fake_tree(bad=None):
    """A Hugging Face tree listing the stub's model bytes as LFS files."""
    entries = []
    for uri in MODELS:
        data = uri.encode()
        oid = hashlib.sha256(data).hexdigest() if bad != "mismatch" else "0" * 64
        entries.append({"path": uri.rsplit("/", 1)[1], "lfs": {"oid": oid, "size": len(data)}})
    return entries


def fake_hf(bad=None):
    """Stands in for run.hf_api_get: HEAD revisions plus trees listing the stub's model bytes."""
    def lookup(path, timeout=15.0, attempts=3):
        if bad == "offline":
            return None, "URLError: <urlopen error offline>"
        if "/tree/" not in path:
            return {"sha": "a" * 40}, None
        return fake_tree(bad), None
    return lookup


# Child-process entry points, so a real signal can stop a run without touching the test
# process. Both give the signals an interactive shell's defaults first. DRIVER calls run.main()
# with only the Hugging Face lookup patched; it can ignore signals, as nohup does for SIGHUP, or
# install a SIGINT handler of its own. Its Hugging Face lookup can also send SIGTERM to its own
# process and then fail, and it can lengthen the runner's stop poll so that a qmd call that ends
# right after a signal finishes before the runner polls. SCRIPT runs run.py as __main__, exactly
# as a shell would.
DRIVER = r'''
import importlib.util, json, os, signal, sys
from unittest import mock
settings = json.loads(sys.argv[1])
spec = importlib.util.spec_from_file_location("rqv2_run", settings["run_py"])
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)
if "stop_poll_seconds" in settings:
    run.STOP_POLL_SECONDS = settings["stop_poll_seconds"]
def hf_api_get(path, timeout=15.0, attempts=3):
    if settings.get("stop_during_hf_lookup"):
        os.kill(os.getpid(), signal.SIGTERM)
        return None, "URLError: <urlopen error offline>"
    return (settings["tree"] if "/tree/" in path else {"sha": "a" * 40}), None
def own_sigint_handler(signum, frame):
    raise KeyboardInterrupt
signal.signal(signal.SIGINT, own_sigint_handler if settings.get("own_sigint_handler") else signal.default_int_handler)
for name in ("SIGTERM", "SIGHUP"):
    signal.signal(getattr(signal, name), signal.SIG_DFL)
for name in settings.get("ignore", []):
    signal.signal(getattr(signal, name), signal.SIG_IGN)
with mock.patch.object(run, "hf_api_get", hf_api_get):
    sys.exit(run.main(settings["argv"]))
'''
SCRIPT = r'''
import json, runpy, signal, sys
settings = json.loads(sys.argv[1])
signal.signal(signal.SIGINT, signal.default_int_handler)
for name in ("SIGTERM", "SIGHUP"):
    signal.signal(getattr(signal, name), signal.SIG_DFL)
sys.argv = [settings["run_py"], *settings["argv"]]
runpy.run_path(settings["run_py"], run_name="__main__")
'''
# Arms StopRequests in a fresh child process and signals that process itself.
STOP_REQUESTS = r'''
import importlib.util, json, os, signal, sys
spec = importlib.util.spec_from_file_location("rqv2_run", sys.argv[1])
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)
signal.signal(signal.SIGINT, signal.default_int_handler)
signal.signal(signal.SIGTERM, signal.SIG_DFL)
signal.signal(signal.SIGHUP, signal.SIG_IGN)
stops = run.StopRequests()
stops.arm()
stops.phase = "arm_b"
stops.current_call = "arm_b:nl-01"
before = stops.requested()
for signum in (signal.SIGTERM, signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
    os.kill(os.getpid(), signum)
try:
    stops.checkpoint()
    raised = None
except run.RunInterrupted as exc:
    raised = exc.signum
stops.restore()
print(json.dumps({
    "before": before,
    "received": [[signal.Signals(s).name, phase, call] for s, _at, phase, call in stops.received],
    "raised": raised,
    "restored": [signal.getsignal(signal.SIGINT) is signal.default_int_handler,
                 signal.getsignal(signal.SIGTERM) is signal.SIG_DFL,
                 signal.getsignal(signal.SIGHUP) is signal.SIG_IGN],
}))
'''


def process_gone(pid, wait=10.0):
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        stat = Path(f"/proc/{pid}/stat")
        if stat.exists() and stat.read_text().split(")")[-1].split()[0] == "Z":
            return True
        time.sleep(0.1)
    return False


class RunnerHarness(unittest.TestCase):
    """Builds the synthetic sealed repository and runs run.main() against the stub."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        # run.py resolves its paths, so compare against the resolved temporary root
        # (macOS places it under the /var -> /private/var symlink).
        self.tmp = Path(directory.name).resolve()
        self.repo = self.tmp / "repo"
        self.out = self.tmp / "out"
        self.home = self.tmp / "scratch-home"
        self.log = self.tmp / "qmd-calls.jsonl"
        for path, text in CORPUS.items():
            target = self.repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        git = ["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
        env = hermetic_git_environment()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True, env=env)
        subprocess.run([*git, "add", "."], check=True, env=env)
        subprocess.run([*git, "commit", "-q", "-m", "corpus"], check=True, env=env)
        commit = subprocess.run([*git, "rev-parse", "HEAD"], check=True, env=env, capture_output=True, text=True).stdout.strip()
        queries = {
            "schema_version": 1,
            "corpus_commit": commit,
            "query_count": len(QUERIES),
            "queries": [
                {"id": qid, "style": style, "query": text, "information_need": text,
                 "relevance": [{"path": p, "grade": g} for p, g in relevance]}
                for qid, style, text, relevance in QUERIES
            ],
            "corpus": [{"path": p, "sha256": SHA[p], "utf8_bytes": len(t.encode())} for p, t in CORPUS.items()],
        }
        self.queries_path = self.repo / M.QUERIES_REL
        self.queries_path.parent.mkdir(parents=True, exist_ok=True)
        self.queries_path.write_text(json.dumps(queries, indent=2))
        seal = hashlib.sha256(self.queries_path.read_bytes()).hexdigest()
        (self.repo / M.PREREG_REL).write_text(f"# Prereg\n\n`queries.json` sha256: `{seal}`.\n")

    def write_stub(self, scenario=None):
        stub_dir = self.tmp / "stub"
        stub_dir.mkdir(exist_ok=True)
        base = {
            "log": str(self.log),
            "models": MODELS,
            "search": {"default": "[]"},
            "query": {"responses": {q[2]: perfect(q[0]) for q in QUERIES}},
            "bench": {"stdout": json.dumps({"summary": {}, "results": []})},
        }
        for key, value in (scenario or {}).items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                merged = dict(base[key])
                for field, setting in value.items():
                    nested = isinstance(setting, dict) and isinstance(merged.get(field), dict)
                    merged[field] = {**merged[field], **setting} if nested else setting
                base[key] = merged
            else:
                base[key] = value
        (stub_dir / "scenario.json").write_text(json.dumps(base))
        (stub_dir / "stub.py").write_text(STUB)
        qmd = stub_dir / "qmd"
        qmd.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{stub_dir / "stub.py"}" "$@"\n')
        qmd.chmod(0o755)
        return qmd

    def argv(self, qmd, extra=()):
        return ["--repo", str(self.repo), "--scratch-home", str(self.home), "--qmd-bin", str(qmd),
                "--output-dir", str(self.out), "--run-id", RUN_ID, "--bootstrap-iterations", "200", *extra]

    def run_main(self, scenario=None, extra=(), caller_env=None, hf=None):
        argv = self.argv(self.write_stub(scenario), extra)
        handled = [getattr(signal, name) for name in ("SIGINT", "SIGTERM", "SIGHUP") if hasattr(signal, name)]
        before = {signum: signal.getsignal(signum) for signum in handled}
        with mock.patch.dict(os.environ, caller_env or {}), mock.patch.object(M, "hf_api_get", hf or fake_hf()), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.exit_code = M.main(argv)
        # main() must give every signal disposition back to its caller.
        self.assertEqual({signum: signal.getsignal(signum) for signum in handled}, before)
        return self.exit_code

    def output(self, kind):
        name = {"results": f"results-{RUN_ID}.json", "native": f"native-{RUN_ID}.json", "report": f"report-{RUN_ID}.md"}[kind]
        path = self.out / name
        return path.read_text() if kind == "report" else json.loads(path.read_text())

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]


class EnvironmentIsolationTests(RunnerHarness):
    def test_env_binds_owned_storage_and_drops_caller_routing(self):
        caller = {"PATH": "/usr/bin", "INDEX_PATH": "/host/.cache/qmd/index.sqlite", "QMD_CONFIG_DIR": "/host/.config/qmd",
                  "QMD_EMBED_MODEL": "hf:x/y/z.gguf", "CI": "true", "HF_ENDPOINT": "https://mirror.invalid",
                  "XDG_CONFIG_HOME": "/host/.config", "HTTPS_PROXY": "http://proxy.invalid:3128", "UNRELATED": "1"}
        env, dropped = M.qmd_env(self.home, "idx", caller)
        self.assertEqual(env["INDEX_PATH"], str(self.home / ".cache/qmd/idx.sqlite"))
        self.assertEqual(env["QMD_CONFIG_DIR"], str(self.home / ".config/qmd"))
        self.assertEqual(env["XDG_CONFIG_HOME"], str(self.home / ".config"))
        self.assertEqual(env["PATH"], "/usr/bin")
        self.assertEqual(env["HTTPS_PROXY"], "http://proxy.invalid:3128")
        for name in ("QMD_EMBED_MODEL", "CI", "HF_ENDPOINT", "UNRELATED"):
            self.assertNotIn(name, env)
        self.assertEqual(dropped, ["CI", "HF_ENDPOINT", "INDEX_PATH", "QMD_CONFIG_DIR", "QMD_EMBED_MODEL", "XDG_CONFIG_HOME"])

    def test_no_qmd_call_follows_the_callers_routing_variables(self):
        decoy = self.tmp / "host"
        caller = {"INDEX_PATH": str(decoy / "index.sqlite"), "QMD_CONFIG_DIR": str(decoy / "config"),
                  "QMD_EMBED_MODEL": "hf:x/y/z.gguf", "CI": "true"}
        self.assertEqual(self.run_main(caller_env=caller), 0)
        self.assertFalse(decoy.exists(), "a qmd call wrote to the caller's routed storage")
        calls = self.calls()
        self.assertTrue(calls)
        for call in calls:
            self.assertEqual(call["cwd"], str(self.home))
            self.assertEqual(call["env"]["INDEX_PATH"], str(self.home / ".cache/qmd/retrieval-quality-v2.sqlite"))
            self.assertEqual(call["env"]["QMD_CONFIG_DIR"], str(self.home / ".config/qmd"))
            self.assertEqual(call["env"]["QMD_FORCE_CPU"], "1")
            for name in ("QMD_EMBED_MODEL", "CI"):
                self.assertNotIn(name, call["env"])
            self.assertEqual(call["argv"][:2], ["--index", "retrieval-quality-v2"], call["argv"])
        self.assertIn(["--index", "retrieval-quality-v2", "pull"], [c["argv"] for c in calls])
        receipt = self.output("results")
        self.assertEqual(receipt["seal"]["preregistration_sha256"],
                         hashlib.sha256((self.repo / M.PREREG_REL).read_bytes()).hexdigest())
        self.assertIn("INDEX_PATH", receipt["environment"]["qmd_env"]["caller_qmd_variables_not_inherited"])
        self.assertEqual(receipt["index"]["content_verification"]["documents_verified"], len(CORPUS))

    def test_index_content_mismatch_aborts_before_any_arm(self):
        self.run_main(scenario={"hash_override": {"notes.md": "f" * 64}})
        receipt = self.output("results")
        self.assertEqual(receipt["status"], "aborted_index_content_mismatch")
        self.assertIsNone(receipt["decision"])
        self.assertFalse([c for c in self.calls() if "search" in c["argv"] or "query" in c["argv"]])
        self.assertIn("Aborted before a decision", self.output("report"))


class ModelPinTests(RunnerHarness):
    def assert_arm_b_closed(self, slug):
        receipt = self.output("results")
        self.assertEqual(receipt["status"], "completed_arm_b_not_run")
        self.assertEqual(receipt["arm_b"]["status"], "not_run")
        self.assertIn(slug, receipt["arm_b"]["not_run_reason"])
        self.assertEqual(receipt["decision"]["decision"], "BM25 (Arm A) stays the default")
        self.assertIsNone(receipt["decision"]["gain_ndcg_at_10"])
        argvs = [c["argv"] for c in self.calls()]
        self.assertFalse([a for a in argvs if "embed" in a or "query" in a or "bench" in a], argvs)

    def test_unresolved_revision_fails_arm_b_closed(self):
        self.assertEqual(self.run_main(hf=fake_hf("offline")), 0)
        self.assert_arm_b_closed("arm_b_model_revision_unresolved")

    def test_revision_that_does_not_hold_the_pulled_bytes_fails_closed(self):
        self.run_main(hf=fake_hf("mismatch"))
        self.assert_arm_b_closed("arm_b_model_revision_mismatch")

    def test_verified_revision_is_recorded(self):
        self.run_main()
        models = self.output("results")["arm_b"]["model_provenance"]["models"]
        self.assertEqual([m["role"] for m in models], ["embed", "generate", "rerank"])
        for model in models:
            self.assertEqual(model["hf_repo_revision"], "a" * 40)
            self.assertEqual(model["hf_revision_lfs_sha256"], model["sha256"])

    def test_qmd_cached_etag_is_read_from_its_uri_file_name(self):
        """QMD caches <file>.etag, not <downloaded file name>.etag (hf_<org>_<file>)."""
        self.run_main()
        models = self.output("results")["arm_b"]["model_provenance"]["models"]
        for uri, model in zip(MODELS, models, strict=True):
            filename = uri.rsplit("/", 1)[1]
            self.assertEqual(model["hf_content_store_etag"],
                             '"' + hashlib.sha256(b"xet:" + uri.encode()).hexdigest() + '"')
            self.assertEqual(model["hf_content_store_etag_path"], f"<SCRATCH_HOME>/.cache/qmd/models/{filename}.etag")
        self.assertEqual(M.qmd_etag_path(Path("/cache"), MODELS[0]), Path("/cache/embeddinggemma-300M-Q8_0.gguf.etag"))


class ResponseValidationTests(RunnerHarness):
    def test_docid_must_match_the_pinned_content_hash(self):
        path = "blueprints/us-equities/data/README.md"
        uri = virtual(path) + "?index=idx"
        good = "#" + SHA[path][:6]
        resolve = M.resolve_repository_path
        self.assertEqual(resolve(uri, good, SHA, "idx"), (path, "ok"))
        self.assertEqual(resolve(uri, good[1:], SHA, "idx")[0], path)
        for docid in ("#000000", "", "#", good[:-1], good.upper(), good + "0", None):
            self.assertIsNone(resolve(uri, docid, SHA, "idx")[0], docid)
        self.assertIsNone(resolve(uri, good, SHA, "other-index")[0])
        self.assertIsNone(resolve(virtual(path).replace("data/", "missing/"), good, SHA, "idx")[0])
        self.assertIsNone(resolve("/abs/" + path, good, SHA, "idx")[0])

    def test_malformed_and_unverifiable_responses_score_zero_and_the_arm_continues(self):
        text = {q[0]: q[2] for q in QUERIES}
        wrong_docid = json.dumps([hit("catalogs/us-equities/notes.md", "#000000")])
        empty_docid = json.dumps([hit("observability/README.md", "")])
        self.run_main(scenario={
            "search": {"responses": {text["kw-01"]: "{}", text["nl-01"]: "[42]", text["pa-01"]: "null",
                                     text["kw-02"]: "not json"}},
            "query": {"responses": {text["nl-01"]: wrong_docid, text["pa-01"]: empty_docid}},
        })
        receipt = self.output("results")
        self.assertEqual(receipt["status"], "completed_both_arms_evaluated")
        arm_a = {r["id"]: r for r in receipt["arm_a"]["per_query"]}
        self.assertEqual(sorted(receipt["arm_a"]["summary"]["errored_queries"]), sorted(arm_a))
        for row in arm_a.values():
            self.assertTrue(row["error"].startswith(("malformed JSON", "malformed hit")), row["error"])
            self.assertEqual((row["ndcg_at_10"], row["recall_at_5"], row["mrr"]), (0.0, 0.0, 0.0))
        arm_b = {r["id"]: r for r in receipt["arm_b"]["per_query"]}
        for qid in ("nl-01", "pa-01"):
            self.assertIn("cannot be verified against the pinned corpus", arm_b[qid]["error"])
            self.assertEqual(arm_b[qid]["ndcg_at_10"], 0.0)
            self.assertEqual(arm_b[qid]["ranked_paths"], [])
        self.assertIn("pinned sha256 prefix", arm_b["nl-01"]["rejected_hits"][0]["reason"])
        self.assertIsNone(arm_b["kw-01"]["error"])
        self.assertAlmostEqual(arm_b["kw-01"]["ndcg_at_10"], 1.0)
        self.assertEqual(sorted(receipt["arm_b"]["summary"]["errored_queries"]), ["nl-01", "pa-01"])

    def test_one_unverifiable_hit_rejects_the_whole_query(self):
        """Amendment 1's rule: the verified hit at rank 1 earns nothing once rank 2 fails
        verification. The 2026-09-25 runner scored rank 2 as grade 0 instead (nDCG@10 0.83)."""
        kw01 = next(q[2] for q in QUERIES if q[0] == "kw-01")
        mixed = json.dumps([hit("blueprints/us-equities/data/README.md"), hit("catalogs/us-equities/notes.md", "#000000")])
        self.run_main(scenario={"query": {"responses": {kw01: mixed}}})
        row = next(r for r in self.output("results")["arm_b"]["per_query"] if r["id"] == "kw-01")
        self.assertEqual((row["ndcg_at_10"], row["recall_at_5"], row["mrr"]), (0.0, 0.0, 0.0))
        self.assertEqual(row["ranked_paths"], [])
        self.assertEqual(row["raw_hit_count"], 2)
        self.assertEqual([r["rank"] for r in row["rejected_hits"]], [2])
        self.assertIn("rank 2 cannot be verified", row["error"])


class TimeoutTests(RunnerHarness):
    def test_pull_timeout_marks_arm_b_not_evaluated_and_kills_the_process_group(self):
        pid_file = self.tmp / "sleeper.pid"
        # 5 s leaves a loaded host time to start the stub and its sleeper before the timeout.
        self.assertEqual(self.run_main(scenario={"pull": {"sleep": 30, "spawn_sleeper": str(pid_file)}},
                                       extra=["--pull-timeout", "5"]), 0)
        receipt = self.output("results")
        self.assertEqual(receipt["status"], "completed_arm_b_not_run")
        self.assertIn("arm_b_pull_timeout", receipt["arm_b"]["not_run_reason"])
        self.assertTrue(pid_file.exists(), "the stub did not start its sleeper within the 5 s timeout")
        self.assertTrue(process_gone(int(pid_file.read_text())), "the timed-out qmd's child process survived")
        pull = next(r for r in self.output("native")["records"] if r["id"] == "arm_b:pull")
        self.assertTrue(pull["timed_out"])
        self.assertIsNone(pull["exit_code"])
        self.assertTrue(pull["process_group_killed"])
        self.assertIsNone(pull["interrupted_by"])
        # Killing only the launcher would leave its child holding the output pipes until
        # the child's own 60 s sleep ended.
        self.assertLess(pull["elapsed_ms"], 30000)
        self.assertIn("Arm B (hybrid) was not evaluated", self.output("report"))

    def test_embed_timeout_marks_arm_b_not_evaluated(self):
        self.run_main(scenario={"embed": {"sleep": 30}}, extra=["--embed-timeout", "1"])
        receipt = self.output("results")
        self.assertIn("arm_b_embed_timeout", receipt["arm_b"]["not_run_reason"])
        self.assertIsNotNone(receipt["arm_b"]["model_provenance"])
        self.assertEqual(receipt["decision"]["decision"], "BM25 (Arm A) stays the default")

    def test_report_renders_aborted_and_partial_receipts(self):
        for receipt in ({}, {"status": "aborted_seal_mismatch", "abort_reason": "x", "decision": None,
                             "arm_a": {"summary": None}, "arm_b": {"status": "not_run"}}):
            self.assertIn("# Retrieval quality v2 run", M.render_report(receipt))


@unittest.skipUnless(hasattr(signal, "SIGHUP") and hasattr(os, "killpg"), "POSIX signals and process groups")
class InterruptTests(RunnerHarness):
    """A real signal stops a child process running run.main() (DRIVER) or run.py itself (SCRIPT)
    while the stub qmd hangs on one call, after writing partial output and starting a
    grandchild in its process group; or the stub signals the runner just before a call ends, or
    the child's patched Hugging Face lookup signals the child. The test process itself is never
    signalled."""

    RUN_PY = ROOT / "blueprints/retrieval-quality-v2/run.py"

    def hang(self, command, query_id, seconds=120, sleeper=True):
        # A grandchild inherits the stub's pipes, so only a call that gets killed may start one.
        text = next(q[2] for q in QUERIES if q[0] == query_id)
        self.marker = self.tmp / "hang.json"
        return {command: {"hang": {text: {"marker": str(self.marker), "sleeper": sleeper, "partial": sleeper,
                                          "seconds": seconds}}}}

    def start(self, scenario, extra=(), entry=DRIVER, **settings):
        """Starts the run in its own session and returns the pids the stub wrote when it hung."""
        payload = {"run_py": str(self.RUN_PY), "argv": self.argv(self.write_stub(scenario), extra),
                   "tree": fake_tree(), **settings}
        self.child = subprocess.Popen([sys.executable, "-c", entry, json.dumps(payload)], stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=True, start_new_session=True)
        self.addCleanup(self.reap)
        deadline = time.monotonic() + 120
        while not self.marker.exists():
            if self.child.poll() is not None or time.monotonic() > deadline:
                self.reap()
                self.fail(f"the stub never reached its hang (exit {self.child.returncode}): {self.child_output}")
            time.sleep(0.05)
        return json.loads(self.marker.read_text())

    def reap(self):
        if self.child.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(self.child.pid, signal.SIGKILL)
        if not hasattr(self, "child_output"):
            self.child_output = self.child.communicate()

    def finish(self):
        self.child_output = self.child.communicate(timeout=120)
        return self.child.returncode, *self.child_output

    def assert_qmd_stopped(self, pids):
        for name, pid in pids.items():
            self.assertTrue(process_gone(pid), f"the stopped qmd call's {name} process survived")

    def test_sigint_stops_an_arm_b_query_and_kills_its_process_group(self):
        """Attempt 20260926T022931Z's stop, replayed: SIGINT while an Arm B query runs."""
        pids = self.start(self.hang("query", "pa-01"))
        os.kill(self.child.pid, signal.SIGINT)
        code, out, err = self.finish()
        self.assertEqual(code, 128 + signal.SIGINT, err)
        self.assertIn("status: aborted_interrupted", out)
        self.assert_qmd_stopped(pids)
        receipt = self.output("results")
        self.assertEqual(receipt["status"], "aborted_interrupted")
        stop = receipt["interruption"]
        self.assertEqual((stop["signal"], stop["phase_when_received"], stop["qmd_call_running_when_received"],
                          stop["cut_short_native_record_id"]), ("SIGINT", "arm_b", "arm_b:pa-01", "arm_b:pa-01"))
        self.assertEqual([(s["signal"], s["qmd_call"]) for s in receipt["signals_received"]], [("SIGINT", "arm_b:pa-01")])
        self.assertIn("arm_b:pa-01", receipt["abort_reason"])
        self.assertEqual(receipt["arm_a"]["status"], "evaluated")
        arm_b = receipt["arm_b"]
        self.assertEqual(arm_b["status"], "interrupted")
        self.assertEqual([r["id"] for r in arm_b["per_query"]], ["kw-01", "nl-01"])
        self.assertIsNone(arm_b["summary"])
        self.assertIsNotNone(arm_b["model_provenance"])
        self.assertIsNone(receipt["decision"])
        self.assertEqual(receipt["native_bench"]["status"], "not_reached")
        self.assertIsNotNone(receipt["durations_seconds"]["arm_b"])
        records = self.output("native")["records"]
        cut = records[-1]
        self.assertEqual(cut["id"], "arm_b:pa-01", "a qmd call started after the stop")
        self.assertEqual((cut["interrupted_by"], cut["exit_code"], cut["timed_out"], cut["process_group_killed"]),
                         ("SIGINT", None, False, True))
        self.assertEqual(cut["stdout"], "[partial stdout before the hang")
        self.assertIn("Expanding query before the hang", cut["stderr"])
        self.assertLess(cut["elapsed_ms"], 60000, "the stub's 120 s hang was not cut short")
        self.assertEqual([r for r in records if r["interrupted_by"]], [cut])
        report = self.output("report")
        self.assertIn("Arm B was interrupted after 2 of 4 queries", report)
        self.assertRegex(report, r"\| nDCG@10 \| [0-9.]+ \| interrupted \|")
        self.assertIn("**Aborted before a decision:** stopped by SIGINT during arm_b", report)

    def test_sigterm_to_the_runner_and_then_its_group_like_gnu_timeout(self):
        """GNU timeout signals the command and then its whole process group. The run records the
        stop, and run.py run as a script then ends by SIGTERM, so its caller sees the stop."""
        pids = self.start(self.hang("search", "kw-02"), extra=["--skip-arm-b"], entry=SCRIPT)
        os.kill(self.child.pid, signal.SIGTERM)
        os.killpg(self.child.pid, signal.SIGTERM)
        code, out, err = self.finish()
        self.assertEqual(code, -signal.SIGTERM, err)
        self.assertIn("status: aborted_interrupted", out)
        self.assert_qmd_stopped(pids)
        receipt = self.output("results")
        self.assertEqual(receipt["status"], "aborted_interrupted")
        self.assertEqual((receipt["interruption"]["signal"], receipt["interruption"]["cut_short_native_record_id"]),
                         ("SIGTERM", "arm_a:kw-02"))
        # The kernel may merge the second SIGTERM into the first while it is pending.
        self.assertIn([s["signal"] for s in receipt["signals_received"]], (["SIGTERM"], ["SIGTERM", "SIGTERM"]))
        self.assertEqual(receipt["arm_a"]["status"], "interrupted")
        self.assertEqual([r["id"] for r in receipt["arm_a"]["per_query"]], ["kw-01", "nl-01", "pa-01"])
        self.assertEqual((receipt["arm_b"]["status"], receipt["native_bench"]["status"]), ("not_reached", "not_reached"))
        self.assertEqual(self.output("native")["records"][-1]["interrupted_by"], "SIGTERM")
        self.assertIn("Arm A was interrupted after 3 of 4 queries", self.output("report"))
        self.assertFalse(list(self.out.glob("*.partial")))

    def test_an_ignored_sighup_is_left_alone(self):
        """Under nohup, SIGHUP stays ignored: the run finishes the hung call and completes."""
        self.start(self.hang("search", "kw-01", seconds=3, sleeper=False), ignore=["SIGHUP"])
        os.kill(self.child.pid, signal.SIGHUP)
        code, _out, err = self.finish()
        self.assertEqual(code, 0, err)
        receipt = self.output("results")
        self.assertEqual(receipt["status"], "completed_both_arms_evaluated")
        self.assertEqual((receipt["interruption"], receipt["signals_received"]), (None, []))
        call = next(r for r in self.output("native")["records"] if r["id"] == "arm_a:kw-01")
        self.assertEqual((call["exit_code"], call["interrupted_by"]), (0, None))

    def test_a_callers_own_sigint_handler_still_leaves_an_interrupted_receipt(self):
        """The runner leaves a caller's SIGINT handler in place; the KeyboardInterrupt that handler
        raises still kills the qmd process group and is recorded."""
        pids = self.start(self.hang("search", "kw-02"), own_sigint_handler=True)
        os.kill(self.child.pid, signal.SIGINT)
        code, _out, err = self.finish()
        self.assertEqual(code, 128 + signal.SIGINT, err)
        self.assert_qmd_stopped(pids)
        receipt = self.output("results")
        self.assertEqual(receipt["status"], "aborted_interrupted")
        stop = receipt["interruption"]
        self.assertEqual((stop["signal"], stop["received_at_utc"], stop["phase_when_received"],
                          stop["qmd_call_running_when_received"], stop["cut_short_native_record_id"]),
                         ("SIGINT", None, "arm_a", "arm_a:kw-02", "arm_a:kw-02"))
        self.assertEqual(receipt["signals_received"], [])
        cut = self.output("native")["records"][-1]
        self.assertEqual((cut["id"], cut["interrupted_by"], cut["exit_code"], cut["process_group_killed"]),
                         ("arm_a:kw-02", "SIGINT", None, True))
        self.assertEqual(receipt["arm_a"]["status"], "interrupted")

    def run_to_end(self, scenario, extra=(), **settings):
        """Runs DRIVER in a child process until it ends; the test sends it no signal."""
        payload = {"run_py": str(self.RUN_PY), "argv": self.argv(self.write_stub(scenario), extra),
                   "tree": fake_tree(), **settings}
        proc = subprocess.run([sys.executable, "-c", DRIVER, json.dumps(payload)], capture_output=True, text=True,
                              timeout=120, start_new_session=True)
        return proc.returncode, proc.stdout, proc.stderr

    def test_a_call_that_ends_after_the_signal_is_named_but_not_cut_short(self):
        """SIGTERM reached the runner while `qmd search` ran nl-01, and that call ended before the runner
        acted on the stop, as in the real-qmd check 20260926T050511Z. run.py 0792745e then wrote "no qmd
        call was in flight"; the receipt must name the call that was running and say nothing was cut short."""
        nl01 = next(q[2] for q in QUERIES if q[0] == "nl-01")
        code, _out, err = self.run_to_end({"search": {"signal_parent": {nl01: "SIGTERM"}}}, extra=["--skip-arm-b"],
                                          stop_poll_seconds=30)
        self.assertEqual(code, 128 + signal.SIGTERM, err)
        receipt = self.output("results")
        reason = receipt["abort_reason"]
        self.assertIn("the qmd call that was running when the signal arrived (arm_a:nl-01) finished before the "
                      "runner acted on the stop, so no qmd call was cut short", reason)
        self.assertNotIn("in flight", reason)
        stop = receipt["interruption"]
        self.assertEqual((stop["signal"], stop["phase_when_received"], stop["qmd_call_running_when_received"],
                          stop["cut_short_native_record_id"]), ("SIGTERM", "arm_a", "arm_a:nl-01", None))
        self.assertEqual([(s["signal"], s["qmd_call"]) for s in receipt["signals_received"]], [("SIGTERM", "arm_a:nl-01")])
        last = self.output("native")["records"][-1]
        self.assertEqual((last["id"], last["exit_code"], last["interrupted_by"], last["process_group_killed"]),
                         ("arm_a:nl-01", 0, None, False))
        self.assertEqual([r["id"] for r in receipt["arm_a"]["per_query"]], ["kw-01", "nl-01"])
        self.assertEqual(receipt["arm_a"]["status"], "interrupted")

    def test_a_stop_during_the_benchmark_keeps_the_decisions_limitations(self):
        """A run stopped while `qmd bench` ran keeps its decision, and the decision keeps its limitations.
        run.py 0792745e assigned every limitation after the benchmark, so this receipt had none."""
        self.marker = self.tmp / "hang.json"
        pids = self.start({"bench": {"hang": {"marker": str(self.marker), "sleeper": True, "partial": True}}})
        os.kill(self.child.pid, signal.SIGTERM)
        code, _out, err = self.finish()
        self.assertEqual(code, 128 + signal.SIGTERM, err)
        self.assert_qmd_stopped(pids)
        receipt = self.output("results")
        limitations = receipt["limitations"]
        self.assertTrue([item for item in limitations if item.startswith("Arm A is QMD's lexical `search` command")],
                        limitations)
        self.assertTrue([item for item in limitations if item.startswith("Arm B's models ran forced onto CPU")], limitations)
        self.assertFalse([item for item in limitations if "`qmd bench`" in item],
                         "a benchmark that returned nothing gets no limitation about its scorer")
        self.assertEqual(receipt["decision"]["decision"], "Hybrid (Arm B) selected over BM25")
        self.assertEqual((receipt["status"], receipt["native_bench"]["status"]), ("aborted_interrupted", "interrupted"))
        self.assertEqual(receipt["interruption"]["cut_short_native_record_id"], "native_bench")
        report = self.output("report")
        self.assertIn("**Stopped after the decision:** stopped by SIGTERM during native_bench", report)
        known = report.split("## Known limitations", 1)[1].split("## Durations", 1)[0]
        self.assertIn("- Arm A is QMD's lexical `search` command", known)

    def test_a_setup_failure_after_a_stop_is_recorded_with_the_stop(self):
        """SIGTERM arrived during Arm B's Hugging Face lookup, which then failed. The failure is part of
        stopping: Arm B is interrupted rather than failed closed, and the stop's reason keeps the failure,
        which run.py 0792745e dropped."""
        code, _out, err = self.run_to_end({}, stop_during_hf_lookup=True)
        self.assertEqual(code, 128 + signal.SIGTERM, err)
        receipt = self.output("results")
        self.assertIn("the run was already stopping when this failure followed: [arm_b_model_revision_unresolved]",
                      receipt["abort_reason"])
        self.assertEqual((receipt["status"], receipt["arm_b"]["status"], receipt["arm_b"]["not_run_reason"]),
                         ("aborted_interrupted", "interrupted", None))
        stop = receipt["interruption"]
        self.assertEqual((stop["signal"], stop["phase_when_received"], stop["qmd_call_running_when_received"],
                          stop["cut_short_native_record_id"]), ("SIGTERM", "arm_b_pull", None, None))
        self.assertIsNone(receipt["decision"])
        self.assertEqual(self.output("native")["records"][-1]["id"], "arm_b:pull", "a qmd call started after the stop")

    def test_stop_requests_record_every_signal_and_raise_only_at_a_checkpoint(self):
        proc = subprocess.run([sys.executable, "-c", STOP_REQUESTS, str(self.RUN_PY)], capture_output=True,
                              text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertFalse(result["before"])
        # SIGHUP was ignored before arm(), so it stays ignored and is never recorded.
        self.assertEqual(result["received"], [["SIGTERM", "arm_b", "arm_b:nl-01"], ["SIGTERM", "arm_b", "arm_b:nl-01"],
                                              ["SIGINT", "arm_b", "arm_b:nl-01"]])
        self.assertEqual(result["raised"], int(signal.SIGTERM))
        self.assertEqual(result["restored"], [True, True, True])

    def test_settled_statuses_and_report_of_a_stopped_run(self):
        receipt = {"status": "aborted_interrupted", "abort_reason": "stopped by SIGTERM during arm_b", "query_count": 30,
                   "decision": None, "arm_a": {"status": "evaluated", "per_query": [], "summary": None},
                   "arm_b": {"status": "running", "per_query": [{"id": "nl-01"}], "summary": None},
                   "native_bench": {"status": "pending"}}
        M.settle_statuses(receipt)
        self.assertEqual((receipt["arm_b"]["status"], receipt["arm_b"]["stop_reason"], receipt["native_bench"]["status"]),
                         ("interrupted", "stopped by SIGTERM during arm_b", "not_reached"))
        self.assertIn("Arm B was interrupted after 1 of 30 queries", M.render_report(receipt))
        failed = {"status": "aborted_zero_idcg", "abort_reason": "x", "arm_a": {"status": "running", "per_query": []},
                  "arm_b": {"status": "pending"}, "native_bench": {"status": "pending"}}
        M.settle_statuses(failed)
        self.assertEqual((failed["arm_a"]["status"], failed["arm_b"]["status"]), ("aborted", "not_reached"))


class OutputTests(RunnerHarness):
    def test_existing_output_is_never_overwritten(self):
        self.out.mkdir()
        existing = self.out / f"native-{RUN_ID}.json"
        existing.write_text("historical\n")
        self.assertEqual(self.run_main(), 2)
        self.assertEqual(existing.read_text(), "historical\n")
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), [existing.name])
        self.assertEqual(self.calls(), [])

    def test_failed_run_writes_its_own_new_receipt_and_keeps_history(self):
        self.out.mkdir()
        history = self.out / "results-20260925.json"
        history.write_text('{"status": "completed_both_arms_evaluated"}\n')
        self.queries_path.write_text(self.queries_path.read_text() + " ")
        self.assertEqual(self.run_main(), 1)
        self.assertEqual(history.read_text(), '{"status": "completed_both_arms_evaluated"}\n')
        receipt = self.output("results")
        self.assertEqual(receipt["status"], "aborted_seal_mismatch")
        self.assertIn("Aborted before a decision", self.output("report"))
        self.assertFalse(list(self.out.glob("*.partial")))

    def test_run_id_must_be_a_utc_timestamp(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(M.main(["--run-id", "../escape", "--output-dir", str(self.out)]), 2)
        self.assertFalse(self.out.exists())


class NativeRetentionTests(RunnerHarness):
    def test_every_scored_query_links_to_its_retained_native_output(self):
        """Every scored query links to its native record, and no host path reaches any output. qmd's
        text here carries host paths in a rejected hit (nl-01: another user's home; kw-02: the scratch
        HOME), in its version banner and in a `qmd pull` note; run.py 0792745e kept the rejected hits'
        reasons, the banner and the note unsanitized."""
        text = {q[0]: q[2] for q in QUERIES}
        outside = {"docid": "#000000", "score": 0.9, "file": "/home/example-user/private/report.md", "title": "t"}
        in_scratch = {"docid": "#000000", "score": 0.9, "file": f"qmd://rqv2-foundation/{self.home}/private.md",
                      "title": "t"}
        self.run_main(scenario={
            "version": "qmd 2.8.3 (/home/example-user/qmd-build)",
            "pull_note": "cached in /home/example-user/models",
            "query": {"stderr": {text["pa-01"]: "Strong BM25 signal (0.93) - skipping expansion\n"},
                      "responses": {text["nl-01"]: json.dumps([outside]), text["kw-02"]: json.dumps([in_scratch])}},
        })
        receipt = self.output("results")
        records = {r["id"]: r for r in self.output("native")["records"]}
        corpus_sha = {p: s for p, s in SHA.items()}
        for arm in ("arm_a", "arm_b"):
            for row in receipt[arm]["per_query"]:
                record = records[row["native_record_id"]]
                self.assertEqual(record["exit_code"], 0)
                self.assertEqual(row["stdout_sha256"], record["stdout_sha256"])
                self.assertEqual(hashlib.sha256(record["stdout"].encode()).hexdigest(), record["stdout_sha256"])
                if row["error"] is not None:  # a rejected response keeps no ranked paths
                    self.assertEqual((row["ranked_paths"], row["ndcg_at_10"]), ([], 0.0))
                    continue
                self.assertTrue(record["stdout_identical_to_raw"])
                hits = json.loads(record["stdout"])
                rederived = [M.resolve_repository_path(h["file"], h["docid"], corpus_sha, "retrieval-quality-v2")[0]
                             for h in hits]
                self.assertEqual(rederived, row["ranked_paths"])
        rejected = {r["id"]: r["rejected_hits"] for r in receipt["arm_b"]["per_query"] if r["rejected_hits"]}
        self.assertEqual(sorted(rejected), ["kw-02", "nl-01"])
        self.assertEqual(rejected["nl-01"][0]["reason"], "unexpected file field (no qmd:// prefix): '~/private/report.md'")
        self.assertIn("<SCRATCH_HOME>/private.md", rejected["kw-02"][0]["reason"])
        self.assertEqual(receipt["qmd_version_raw"], "qmd 2.8.3 (~/qmd-build)")
        self.assertEqual({m["pull_note"] for m in receipt["arm_b"]["model_provenance"]["models"]}, {"cached in ~/models"})
        self.assertEqual(receipt["arm_b"]["expansion_skipped_queries"], ["pa-01"])
        add = records["index:collection-add:rqv2-foundation"]
        self.assertIn("<SCRATCH_HOME>/corpus-stage/blueprints/us-equities", add["argv"])
        dumped = json.dumps(self.output("native")) + json.dumps(receipt) + self.output("report")
        self.assertNotIn(str(self.home), dumped)
        self.assertNotIn(str(self.repo), dumped)
        self.assertNotIn("/home/example-user", dumped)


class NativeBenchTests(RunnerHarness):
    def bench_output(self):
        """`qmd bench --json` output for every fixture query on each of QMD's four backends
        (src/bench/bench.ts runs all four for every query)."""
        results = []
        for qid, _style, text, relevance in QUERIES:
            full_top = [virtual(p) for p, _grade in sorted(relevance, key=lambda r: -r[1])]
            # A collection-root README.md suffix-matches the nested data/README.md in
            # QMD's scorer; the exact audit must not credit it.
            root_readme = [virtual("blueprints/us-equities/README.md")]
            bm25_top = root_readme if qid in ("kw-01", "kw-02") else []
            full = {"top_files": full_top, "recall_at_5": 1.0, "mrr": 1.0}
            results.append({"id": qid, "query": text, "type": "exact", "backends": {
                "bm25": {"top_files": bm25_top, "recall_at_5": 1.0 if bm25_top else 0.0,
                         "mrr": 1.0 if bm25_top else 0.0},
                "vector": dict(full), "hybrid": dict(full), "full": full,
            }})
        summary = {name: {"avg_precision": 0.5, "avg_recall_at_5": 0.5, "avg_mrr": 0.5, "avg_latency_ms": 1.0}
                   for name in M.BENCH_BACKENDS}
        return json.dumps({"timestamp": "x", "fixture": "f", "results": results, "summary": summary})

    def test_empty_or_incomplete_bench_output_is_not_completed(self):
        """run.py 0792745e accepted `{"summary": {}, "results": []}` as a completed benchmark of all four
        backends with zero queries. Output must hold every fixture query, once, on every backend."""
        complete = json.loads(self.bench_output())
        missing_query = dict(complete, results=complete["results"][:-1])
        duplicated_query = dict(complete, results=complete["results"] + complete["results"][:1])
        missing_backend = json.loads(self.bench_output())
        del missing_backend["results"][1]["backends"]["vector"]
        summary_short = json.loads(self.bench_output())
        del summary_short["summary"]["hybrid"]
        cases = {
            "empty": ({"summary": {}, "results": []}, "no result for fixture queries kw-01, nl-01, pa-01, kw-02"),
            "missing query": (missing_query, "no result for fixture queries kw-02"),
            "duplicated query": (duplicated_query, "more than one result for kw-01"),
            "missing backend": (missing_backend, "no vector result with a top_files list for nl-01"),
            "summary lacks a backend": (summary_short, "no summary for backends hybrid"),
        }
        for name, (document, expected) in cases.items():
            with self.subTest(name):
                shutil.rmtree(self.out, ignore_errors=True)
                self.assertEqual(self.run_main(scenario={"bench": {"stdout": json.dumps(document)}}), 0)
                receipt = self.output("results")
                bench = receipt["native_bench"]
                self.assertEqual(bench["status"], "incomplete")
                self.assertIn(expected, bench["error"])
                self.assertNotIn("exact_identity_audit", bench)
                self.assertNotIn("native_summary", bench)
                self.assertEqual(receipt["status"], "completed_both_arms_evaluated")
                self.assertEqual(receipt["decision"]["decision"], "Hybrid (Arm B) selected over BM25")
                report = self.output("report")
                self.assertIn("Status `incomplete`", report)
                self.assertNotIn("ran all four upstream backends", report)

    def test_bench_runs_on_the_same_index_with_a_derived_fixture_and_an_exact_audit(self):
        self.run_main(scenario={"bench": {"stdout": self.bench_output()}})
        receipt = self.output("results")
        bench = receipt["native_bench"]
        self.assertEqual(bench["status"], "completed")
        self.assertEqual(bench["evidence_class"], "upstream_native_operation")
        bench_call = next(c for c in self.calls() if "bench" in c["argv"])
        self.assertEqual(bench_call["argv"][:3], ["--index", "retrieval-quality-v2", "bench"])
        self.assertEqual(bench_call["argv"][-1], "--json")
        fixture = json.loads(Path(bench_call["argv"][3]).read_text())
        self.assertEqual(M.sha256_bytes((json.dumps(fixture, indent=2) + "\n").encode()), bench["fixture"]["sha256"])
        first = fixture["queries"][0]
        self.assertEqual((first["id"], first["expected_files"], first["expected_in_top_k"]),
                         ("kw-01", ["qmd://rqv2-foundation/data/README.md"], 5))
        audit = bench["exact_identity_audit"]
        self.assertEqual(audit["bm25"]["native_vs_exact_recall_at_5_disagreements"], ["kw-01"])
        self.assertEqual(audit["full"]["native_vs_exact_recall_at_5_disagreements"], [])
        self.assertEqual(audit["full"]["cli_rankings_identical"], audit["full"]["cli_rankings_compared"])
        self.assertEqual(audit["bm25"]["cli_arm"], "arm_a")
        self.assertIn("QMD's own benchmark", self.output("report"))

    def test_bench_failure_is_recorded_without_touching_the_decision(self):
        self.assertEqual(self.run_main(scenario={"bench": {"stdout": "boom", "exit": 1}}), 0)
        receipt = self.output("results")
        self.assertEqual(receipt["native_bench"]["status"], "failed")
        self.assertEqual(receipt["status"], "completed_both_arms_evaluated")
        self.assertEqual(receipt["decision"]["decision"], "Hybrid (Arm B) selected over BM25")


class CommittedRunEvidenceTests(unittest.TestCase):
    """Structural check of the committed runs: every schema-2 receipt must re-derive from its
    own retained native qmd output, with metrics recomputed here rather than by run.py."""

    BLUEPRINT = ROOT / "blueprints/retrieval-quality-v2"

    @staticmethod
    def ndcg(paths, relevance):
        grades = {r["path"]: r["grade"] for r in relevance}
        gain = sum((2 ** grades.get(p, 0) - 1) / math.log2(i + 2) for i, p in enumerate(paths[:10]))
        ideal = sorted(grades.values(), reverse=True)[:10]
        return gain / sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))

    def test_committed_receipts_rederive_from_their_native_output(self):
        sealed = json.loads((self.BLUEPRINT / "queries.json").read_text())
        queries = {q["id"]: q for q in sealed["queries"]}
        pins = {d["path"]: d["sha256"] for d in sealed["corpus"]}
        receipts = [p for p in sorted(self.BLUEPRINT.glob("results-*.json"))
                    if json.loads(p.read_text()).get("schema_version", 1) >= 2]
        self.assertTrue(receipts, "no schema-2 receipt is committed")
        for path in receipts:
            receipt = json.loads(path.read_text())
            native = json.loads((self.BLUEPRINT / receipt["outputs"]["native"]).read_text())
            records = {r["id"]: r for r in native["records"]}
            self.assertEqual(native["results_file"], path.name)
            for arm in ("arm_a", "arm_b"):
                for row in receipt[arm]["per_query"]:
                    record = records[row["native_record_id"]]
                    self.assertEqual(hashlib.sha256(record["stdout"].encode()).hexdigest(), row["stdout_sha256"])
                    self.assertEqual(record["exit_code"], row["exit_code"])
                    if row["error"] is not None:
                        self.assertEqual((row["ndcg_at_10"], row["recall_at_5"], row["mrr"]), (0.0, 0.0, 0.0))
                        continue
                    paths = []
                    for hit in json.loads(record["stdout"])[:10]:
                        path_part = hit["file"][len("qmd://"):].split("?")[0]
                        collection, relative = path_part.split("/", 1)
                        repository_path = f"{M.COLLECTION_PREFIX[collection]}/{relative}"
                        self.assertEqual(pins[repository_path][:6], hit["docid"].lstrip("#"))
                        paths.append(repository_path)
                    self.assertEqual(paths, row["ranked_paths"], f"{path.name} {arm} {row['id']}")
                    relevance = queries[row["id"]]["relevance"]
                    grade2 = [r["path"] for r in relevance if r["grade"] == 2]
                    relevant = [r["path"] for r in relevance if r["grade"] >= 1]
                    first = next((i for i, p in enumerate(paths) if p in relevant), None)
                    self.assertAlmostEqual(row["ndcg_at_10"], self.ndcg(paths, relevance), places=12)
                    self.assertAlmostEqual(row["recall_at_5"], sum(p in paths[:5] for p in grade2) / len(grade2), places=12)
                    self.assertAlmostEqual(row["mrr"], 0.0 if first is None else 1 / (first + 1), places=12)
            if receipt["arm_b"]["status"] == "evaluated":
                means = {arm: sum(r["ndcg_at_10"] for r in receipt[arm]["per_query"]) / len(receipt[arm]["per_query"])
                         for arm in ("arm_a", "arm_b")}
                self.assertAlmostEqual(receipt["decision"]["gain_ndcg_at_10"], means["arm_b"] - means["arm_a"], places=12)


if __name__ == "__main__":
    unittest.main()
