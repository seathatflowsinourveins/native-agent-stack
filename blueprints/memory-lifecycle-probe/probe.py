#!/usr/bin/env python3
"""Sanitized publication driver; not the byte-identical executed original.

Set AI_MEMORY_BIN explicitly. Original executed-script hash is in provenance.json.
Tiny native CLI lifecycle probe, restricted to this disposable /tmp prefix.

Source and packages must be provisioned separately at the documented pins.
No active memory, inherited credentials, embeddings or LLM are used.
"""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "evidence/artifacts/memory-lifecycle-probe-20260921"
SCRATCH = Path("/tmp/memory-lifecycle-probe-20260921-scratch")
AI = os.environ["AI_MEMORY_BIN"]
BM = str(SCRATCH / "venv/bin/bm")
BASE_ENV = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "NO_COLOR": "1"}
CORPUS_PATH = Path(__file__).with_name("corpus.json")
CORPUS = json.loads(CORPUS_PATH.read_text())
EVENTS = []


def run(label, argv, env, body=None, expected=0):
    started = time.monotonic()
    p = subprocess.run(argv, env=env, cwd=SCRATCH, input=body,
                       capture_output=True, text=True, timeout=60)
    event = {"label": label, "argv": argv, "environment": env,
             "stdin": body, "exit_code": p.returncode,
             "elapsed_seconds": round(time.monotonic() - started, 6),
             "stdout": p.stdout, "stderr": p.stderr}
    EVENTS.append(event)
    (ART / "commands.json").write_text(json.dumps(EVENTS, indent=2) + "\n")
    print(label, p.returncode, flush=True)
    if expected is not None and p.returncode != expected:
        raise RuntimeError(f"{label}: exit {p.returncode}; see commands.json")
    return p.stdout


def start_ai(data, port, number):
    env = dict(BASE_ENV, AI_MEMORY_SERVER_URL=f"http://127.0.0.1:{port}",
               AI_MEMORY_EMBEDDING_PROVIDER="none")
    argv = [AI, "--data-dir", str(data), "serve", "--transport", "http",
            "--bind", f"127.0.0.1:{port}", "--no-watcher",
            "--workspace", "probe", "--project", "synthetic"]
    log = (ART / f"ai-server-{number}.log").open("w")
    server = subprocess.Popen(argv, env=env, cwd=SCRATCH, stdout=log, stderr=log)
    EVENTS.append({"label": f"ai-server-{number}", "argv": argv,
                   "environment": env, "pid": server.pid})
    for _ in range(100):
        if server.poll() is not None:
            log.close()
            raise RuntimeError("Isolated ai-memory server exited; see server log")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=.1):
                return server, log, env
        except OSError:
            time.sleep(.1)
    server.terminate()
    server.wait(timeout=10)
    log.close()
    raise RuntimeError("Isolated ai-memory server did not become ready")


def stop_ai(server, log):
    server.terminate()
    server.wait(timeout=10)
    log.close()


def ai_lifecycle():
    data = SCRATCH / "ai-state-no-embedding"
    if data.exists():
        raise RuntimeError("Refusing to reuse prior ai-memory probe store")
    run("ai-version", [AI, "--version"], BASE_ENV)
    run("ai-init", [AI, "--data-dir", str(data), "init"], BASE_ENV)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server, log, env = start_ai(data, port, 1)
    scope = ["--workspace", "probe", "--project", "synthetic"]
    def call(label, verb, *args, body=None):
        return run(label, [AI, "--data-dir", str(data), verb, *args, *scope], env, body)
    try:
        for p in CORPUS["pages"]:
            call("ai-write-" + p["slug"], "write-page", "--path", f"notes/{p['slug']}.md", "--body", "-", body=p["body"])
        for q in CORPUS["queries"]:
            call("ai-search-" + q["query"], "search", q["query"], "--json")
            call("ai-read-" + q["expected_slug"], "read-page", "--path", f"notes/{q['expected_slug']}.md", "--json")
        u = CORPUS["update"]
        call("ai-update", "write-page", "--path", f"notes/{u['slug']}.md", "--body", "-", body=u["body"])
        call("ai-search-updated", "search", u["new_query"], "--json")
        call("ai-search-old", "search", u["old_query"], "--json")
        call("ai-read-updated", "read-page", "--path", f"notes/{u['slug']}.md", "--json")
        d = CORPUS["delete"]
        call("ai-delete", "delete-page", "--path", f"notes/{d['slug']}.md")
        call("ai-search-deleted", "search", d["query"], "--json")
        run("ai-backup", [AI, "--data-dir", str(data), "backup", "--to", str(SCRATCH / "ai-backup-no-embedding.tar.gz")], env)
    finally:
        stop_ai(server, log)
    server, log, env = start_ai(data, port, 2)
    try:
        call("ai-after-restart-updated", "read-page", "--path", "notes/orchard-pump.md", "--json")
        call("ai-after-restart-remaining", "search", "cobalt", "--json")
        call("ai-after-restart-deleted", "search", "Juniper", "--json")
    finally:
        stop_ai(server, log)


def basic_lifecycle():
    env = dict(BASE_ENV,
        BASIC_MEMORY_CONFIG_DIR=str(SCRATCH / "basic-state"),
        BASIC_MEMORY_HOME=str(SCRATCH / "basic-notes"),
        BASIC_MEMORY_SEMANTIC_SEARCH_ENABLED="false")
    run("basic-project", [BM, "project", "add", "synthetic", str(SCRATCH / "basic-synthetic"), "--local"], env)
    def call(label, verb, *args, body=None):
        return run(label, [BM, "tool", verb, *args, "--project", "synthetic", "--local"], env, body)
    for p in CORPUS["pages"]:
        call("basic-write-" + p["slug"], "write-note", "--title", p["title"], "--folder", "notes", body=p["body"])
    for q in CORPUS["queries"]:
        call("basic-search-" + q["query"], "search-notes", q["query"], "--json")
        call("basic-read-" + q["expected_slug"], "read-note", f"notes/{q['expected_slug']}", "--json")
    u = CORPUS["update"]
    call("basic-update", "write-note", "--title", u["title"], "--folder", "notes", "--overwrite", body=u["body"])
    call("basic-search-updated", "search-notes", u["new_query"], "--json")
    call("basic-search-old", "search-notes", u["old_query"], "--json")
    call("basic-read-updated", "read-note", "notes/orchard-pump", "--json")
    d = CORPUS["delete"]
    call("basic-delete", "delete-note", f"notes/{d['slug']}")
    call("basic-search-deleted", "search-notes", d["query"], "--json")
    run("basic-reindex", [BM, "reindex", "--full", "--search", "--project", "synthetic"], env)
    call("basic-after-reindex-updated", "read-note", "notes/orchard-pump", "--json")
    call("basic-after-reindex-remaining", "search-notes", "cobalt", "--json")
    call("basic-after-reindex-deleted", "search-notes", "Juniper", "--json")


if __name__ == "__main__":
    ART.mkdir(parents=True, exist_ok=True)
    (ART / "frozen-corpus-sha256.txt").write_text(hashlib.sha256(CORPUS_PATH.read_bytes()).hexdigest() + "  corpus.json\n")
    try:
        # Basic Memory already completed under explicit semantic-search=false.
        # Preserve its original measured commands; rerun only the rejected lane.
        first_attempt = json.loads((ART / "attempt-1-default-embedding/commands.json").read_text())
        EVENTS.extend(e for e in first_attempt if e["label"].startswith("basic-"))
        ai_lifecycle()
    finally:
        (ART / "commands.json").write_text(json.dumps(EVENTS, indent=2) + "\n")
