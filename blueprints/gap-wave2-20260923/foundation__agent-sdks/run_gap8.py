#!/usr/bin/env python3
"""Run the three gap-8 durable-runtime checks and record exit codes and installed versions.

Usage: run_gap8.py CACHE_DIR RUNS_DIR PRIOR_TEMPORAL_CLI_DIR
Each check runs in its own venv under CACHE_DIR; outputs land in RUNS_DIR; the
Temporal CLI already downloaded into PRIOR_TEMPORAL_CLI_DIR is hard-linked so no
second download happens. Writes RUNS_DIR/gap8-runs.json.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE, RUNS, PRIOR_CLI = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
BOUNDED = str(Path.home() / "codex-ecosystem/bin/ecosystem-bounded-run")


def versions(venv: str, names: list[str]) -> dict:
    code = "import importlib.metadata as m, json, sys; print(json.dumps({n: m.version(n) for n in sys.argv[1:]}))"
    out = subprocess.run([str(CACHE / venv / "bin/python"), "-c", code, *names], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def run(label: str, argv: list[str], env: dict | None = None) -> dict:
    started = time.time()
    proc = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=600)
    return {"label": label, "exit_code": proc.returncode, "seconds": round(time.time() - started, 2),
            "stdout_tail": proc.stdout[-600:]}


def main() -> int:
    rec: dict = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "runs": []}
    rec["versions"] = {"langgraph": versions("langgraph", ["langgraph", "langgraph-checkpoint-sqlite"]),
                       "temporal": versions("temporal", ["temporalio"]),
                       "openhands": versions("openhands", ["openhands-sdk", "openhands-tools", "litellm"])}
    lg = Path(tempfile.mkdtemp(prefix="lg-", dir=CACHE))
    py = str(CACHE / "langgraph/bin/python")
    rec["runs"].append(run("langgraph_start", [py, str(HERE / "langgraph_checkpoint.py"), "start", str(lg / "cp.sqlite"), str(RUNS / "langgraph-start.json")]))
    rec["runs"].append(run("langgraph_resume", [py, str(HERE / "langgraph_checkpoint.py"), "resume", str(lg / "cp.sqlite"), str(RUNS / "langgraph-resume.json")]))
    tw = Path(tempfile.mkdtemp(prefix="tmp-", dir=CACHE))
    subprocess.run(["cp", "-al", str(PRIOR_CLI), str(tw / "cli")], check=True)
    cli_bin = next((p for p in (tw / "cli").rglob("*") if p.is_file() and p.stat().st_mode & 0o111), None)
    if cli_bin:
        rec["temporal_cli_version"] = subprocess.run([str(cli_bin), "--version"], capture_output=True, text=True).stdout.strip()
    rec["runs"].append(run("temporal_controller", [BOUNDED, str(CACHE / "temporal/bin/python"), str(HERE / "temporal_restart.py"),
                                                   "controller", str(tw), str(RUNS / "temporal-restart.json")]))
    oh = Path(tempfile.mkdtemp(prefix="oh-", dir=CACHE))
    (oh / "ws").mkdir(); (oh / "persist").mkdir()
    env = {"HOME": str(oh / "home"), "PATH": "/usr/bin:/bin", "OPENHANDS_SUPPRESS_BANNER": "1"}
    for phase in ("first", "reload"):
        rec["runs"].append(run(f"openhands_{phase}", [str(CACHE / "openhands/bin/python"), str(HERE / "openhands_local.py"), phase,
                                                     str(oh / "ws"), str(oh / "persist"), str(RUNS / f"openhands-{phase}.json")], env))
    rec["sizes_on_disk"] = {name: subprocess.run(["du", "-sh", str(CACHE / name)], capture_output=True, text=True).stdout.split()[0]
                            for name in ("codex-sdk-01551", "claude-sdk", "openhands", "langgraph", "temporal")}
    rec["sizes_on_disk"]["temporal_cli_dir"] = subprocess.run(["du", "-sh", str(PRIOR_CLI)], capture_output=True, text=True).stdout.split()[0]
    rec["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (RUNS / "gap8-runs.json").write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps({r["label"]: r["exit_code"] for r in rec["runs"]}))
    return 0 if all(r["exit_code"] == 0 for r in rec["runs"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
