#!/usr/bin/env python3
"""Rollback probe for the Codex state databases (run inside sandbox.sh; scratch CODEX_HOME only).

Usage: rollback_probe.py <old-codex> <new-codex> <arm-dir> <results.json>

  M1 old version: one fake-provider exec turn on an empty CODEX_HOME (creates the state databases)
  M2 new version: one turn on the same CODEX_HOME (applies its newer sqlx migrations)
  M3 old version again on the migrated CODEX_HOME: does it still run a turn, and what does it report?
After each step the applied migration counts of every *.sqlite file are recorded (read-only).
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

old, new, arm, results_path = sys.argv[1], sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
here = Path(__file__).resolve().parent
PORT = 18092
home = arm / "mig-home"
home.mkdir(parents=True)
(arm / "empty").mkdir(exist_ok=True)
provider = ["-c", 'model_provider="fakeprov"', "-c", 'model_providers.fakeprov.name="fake"',
            "-c", f'model_providers.fakeprov.base_url="http://127.0.0.1:{PORT}/v1"',
            "-c", 'model_providers.fakeprov.wire_api="responses"', "-c", "model_providers.fakeprov.request_max_retries=0",
            "-c", "model_providers.fakeprov.stream_max_retries=0"]
out = {"steps": []}


def migrations() -> dict:
    counts = {}
    for db in sorted(home.glob("*.sqlite")):
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
            rows = con.execute("select version from _sqlx_migrations order by version").fetchall()
            counts[db.name] = [len(rows), rows[-1][0] if rows else None]
            con.close()
        except Exception as exc:  # noqa: BLE001
            counts[db.name] = f"error: {exc}"
    return counts


server = subprocess.Popen([sys.executable, str(here / "fake_responses.py"), str(PORT), "ok", str(arm / "mig-requests.jsonl")],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
time.sleep(0.8)
for step, binary in (("M1-old", old), ("M2-new", new), ("M3-old-on-migrated", old)):
    argv = [binary, "exec", "--ignore-user-config", "--skip-git-repo-check", "-s", "read-only", "-m", "gpt-6-astra"] + \
        provider + ["--json", "Reply with one word."]
    proc = subprocess.run(argv, cwd=arm / "empty", env=dict(os.environ, CODEX_HOME=str(home)),
                          stdin=subprocess.DEVNULL, capture_output=True, timeout=180)
    events = []
    for line in proc.stdout.decode(errors="replace").splitlines():
        try:
            events.append(json.loads(line).get("type"))
        except ValueError:
            events.append("<non-json>")
    record = {"step": step, "binary": binary.replace(str(Path.home()), "~"), "exit": proc.returncode,
              "event_types": events, "stderr_tail": proc.stderr.decode(errors="replace")[-700:].replace(str(arm), "<arm>"),
              "migrations_after": migrations()}
    out["steps"].append(record)
    print(json.dumps(record)[:1500], flush=True)
server.terminate()
server.wait(timeout=10)
results_path.write_text(json.dumps(out, indent=2) + "\n")
print("DONE")
