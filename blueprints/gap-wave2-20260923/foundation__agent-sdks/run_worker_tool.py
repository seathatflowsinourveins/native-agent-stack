#!/usr/bin/env python3
"""Fix round 2: persistent tool turn then new-process resume, both through native_worker.py.

Usage: run_worker_tool.py CACHE_DIR RUNS_DIR
Turn 1 (--persistent --lookup-tool) must call the worker's registered custom tool
and store its random value; turn 2 (--resume-thread-id, new process) gets a decoy
tool file, so any tool call in turn 2 is recorded and would return a different
value. Before each model call this waits while 2 or more real `codex exec`
processes run (classified by argv, not by substring). It lists
~/.codex/context-mode and ~/.codex/sessions (name, size, mtime) before and after,
so side effects can be enumerated. Writes RUNS_DIR/worker-tool-runs.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKER = ROOT / "blueprints/us-equities/workers/native_worker.py"
CACHE, RUNS = Path(sys.argv[1]), Path(sys.argv[2])
HOME = Path.home()
PY = CACHE / "codex-sdk-01551/bin/python"
CODEX_BIN = HOME / ".local/share/codex-ecosystem/bin/codex"
ISO_PLUGIN = ["--config-override", "features.hooks=false", "--config-override", "features.plugin_hooks=false",
              "--config-override", "features.apps=false", "--config-override", 'otel.exporter="none"',
              "--config-override", 'otel.metrics_exporter="none"', "--config-override", "analytics.enabled=false",
              "--config-override", 'plugins={"context-mode@context-mode"={enabled=false}}']


def real_codex_exec() -> list[str]:
    """Processes whose argv is `<codex|codex.js> exec ...`; sandbox helpers and shells are excluded."""
    out = subprocess.run(["ps", "-eo", "pid=,args="], capture_output=True, text=True).stdout
    hits = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        argv = parts[1:]
        if Path(argv[0]).name == "node" and len(argv) > 2:
            argv = argv[1:]
        if Path(argv[0]).name in ("codex", "codex.js") and argv[1] == "exec":
            hits.append(parts[0] + " " + Path(argv[0]).name + " exec")
    return hits


def wait_for_slot(log: list) -> None:
    for _ in range(120):
        procs = real_codex_exec()
        log.append({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "real_codex_exec": len(procs)})
        if len(procs) < 2:
            return
        time.sleep(10)
    raise SystemExit("codex exec slot never freed")


def listing(root: Path) -> dict:
    return {str(p.relative_to(root)): [p.stat().st_size, round(p.stat().st_mtime, 3)]
            for p in sorted(root.rglob("*")) if p.is_file()} if root.is_dir() else {}


def snapshot() -> dict:
    return {"context-mode": listing(HOME / ".codex/context-mode"), "sessions": listing(HOME / ".codex/sessions")}


def diff(before: dict, after: dict) -> dict:
    out = {}
    for area in before:
        b, a = before[area], after[area]
        out[area] = {"added": sorted(set(a) - set(b)), "removed": sorted(set(b) - set(a)),
                     "changed": sorted(k for k in set(a) & set(b) if a[k] != b[k])}
    return out


def worker(receipt: Path, prompt: Path, extra: list[str]) -> dict:
    argv = [str(PY), str(WORKER), "run", "--codex-bin", str(CODEX_BIN), "--codex-home", str(HOME / ".codex"),
            "--workspace", str(CACHE / "ws-probe"), "--prompt", str(prompt), "--receipt", str(receipt),
            "--turn-deadline-seconds", "180", *extra, *ISO_PLUGIN]
    env = {"HOME": str(HOME), "PATH": f"{HOME}/.local/share/codex-ecosystem/bin:/usr/bin:/bin"}
    started = time.time()
    proc = subprocess.run(["timeout", "--signal=TERM", "--kill-after=10s", "300s", *argv],
                          capture_output=True, text=True, env=env)
    return {"exit_code": proc.returncode, "seconds": round(time.time() - started, 2),
            "stdout": proc.stdout[-400:], "stderr_tail_lines": len(proc.stderr.splitlines())}


def main() -> int:
    value = "vw-" + secrets.token_hex(6)
    spec = {"name": "vault_lookup", "description": "Return the stored value for a key from the caller's private vault."}
    real, decoy = RUNS / "worker-tool-values.json", RUNS / "worker-tool-decoy.json"
    for path, v in ((real, value), (decoy, "decoy-not-the-value")):
        path.write_text(json.dumps({**spec, "values": {"alpha": v}}))
        os.chmod(path, 0o600)
    p1, p2 = RUNS / "worker-tool-t1.prompt", RUNS / "worker-tool-t2.prompt"
    p1.write_text('Call the vault_lookup tool with key "alpha". Remember the exact value it returns for later in '
                  "this conversation. Run no shell commands. Reply with only the word STORED.\n")
    p2.write_text("Without calling any tool or running any command, what exact value did vault_lookup return "
                  "earlier in this conversation? Reply with only that value.\n")
    rec: dict = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "worker_sha256": hashlib.sha256(WORKER.read_bytes()).hexdigest(), "slot_checks": []}
    before = snapshot()
    wait_for_slot(rec["slot_checks"])
    r1 = RUNS / "worker-tool-t1.json"
    rec["t1"] = worker(r1, p1, ["--persistent", "--lookup-tool", str(real)])
    tid = json.loads(r1.read_text()).get("thread_id")
    if tid:
        wait_for_slot(rec["slot_checks"])
        rec["t2"] = worker(RUNS / "worker-tool-t2.json", p2, ["--resume-thread-id", tid, "--lookup-tool", str(decoy)])
    after = snapshot()
    rec["side_effects"] = diff(before, after)
    thread_files = [k for k in rec["side_effects"]["sessions"]["added"] + rec["side_effects"]["sessions"]["changed"]
                    if tid and tid in k]
    rec["own_rollout_files"] = len(thread_files)
    rec["t2_prompt_contains_value"] = value in p2.read_text()
    t2 = json.loads((RUNS / "worker-tool-t2.json").read_text()) if (RUNS / "worker-tool-t2.json").exists() else {}
    rec["t2_final_matches_t1_value"] = (t2.get("final_response") or "").strip().strip("`\"'. ") == value
    rec["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (RUNS / "worker-tool-runs.json").write_text(json.dumps(rec, indent=2) + "\n")
    (RUNS / "worker-tool-state.json").write_text(json.dumps({"value": value}))
    print(json.dumps({k: rec[k] for k in ("t2_final_matches_t1_value", "own_rollout_files")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
