#!/usr/bin/env python3
"""Inventory the host's isolated tool environments and compare their packages with PyPI (evidence, not selection).

  python3 scripts/env_freshness.py --tools-dir ~/.local/share/codex-ecosystem/tools --host-label wsl-main --out report.json
  python3 scripts/env_freshness.py ... --offline-index index.json     # replay PyPI answers (no network)

For every directory under --tools-dir with a bin/python, the environment's own interpreter lists its installed
distributions (importlib.metadata; uv-built venvs have no pip). Packages in the watch list (the trading and
foundation layers: engine, broker SDKs, data, storage, research, workers) are compared with PyPI's latest stable
and latest pre-release, each with its upload date. Status per row: current, behind_stable, prerelease_current
(installed is the newest pre-release), prerelease_behind, ahead_of_index, or unknown. The report names the host
only by --host-label and never records paths outside the tools directory's own entry names, so each PC can publish
its own report and reports from different runtimes compare row by row. This script never installs, upgrades or
removes anything and never decides adoption: the SOTA-convergence lane review owns that.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import platform
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

WATCH = (
    # engine, broker and market data
    "nautilus-trader", "alpaca-py", "ibapi", "ib-async", "databento", "exchange-calendars", "pandas-market-calendars",
    "websockets", "msgpack",
    # storage and compute
    "duckdb", "pyarrow", "polars", "pandas", "numpy", "deltalake", "arcticdb", "dvc",
    # research and evaluation
    "scipy", "statsmodels", "scikit-learn", "vectorbt", "quantstats", "pandera", "edgartools",
    # workers and model runtimes
    "claude-agent-sdk", "openai-codex", "vllm", "torch",
)
LIST_CODE = ("import json, importlib.metadata as m, sys; print(json.dumps({'python': sys.version.split()[0], "
             "'dists': {d.metadata['Name'].lower(): d.version for d in m.distributions() if d.metadata['Name']}}))")
PRE = re.compile(r"(a|b|rc|dev)\d*", re.I)


def version_key(v: str):
    """Sortable key for the common PEP 440 shapes (release, then pre-release after dev, before final)."""
    m = re.match(r"^(\d+(?:\.\d+)*)(?:\.?(a|b|rc|dev)(\d*))?", v)
    if not m:
        return ((), 9, 0)
    rel = tuple(int(x) for x in m.group(1).split("."))
    rel = rel + (0,) * (6 - len(rel))
    order = {"dev": 0, "a": 1, "b": 2, "rc": 3, None: 4}[m.group(2).lower() if m.group(2) else None]
    return (rel, order, int(m.group(3) or 0))


def list_env(env: Path, runner=subprocess.run) -> dict | None:
    py = env / "bin" / "python"
    if not py.exists():
        return None
    out = runner([str(py), "-c", LIST_CODE], capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        return {"error": (out.stderr or "").strip().splitlines()[-1:] or ["failed"]}
    return json.loads(out.stdout)


def pypi_latest(name: str, fetch=None) -> dict:
    fetch = fetch or (lambda n: json.loads(urllib.request.urlopen(f"https://pypi.org/pypi/{n}/json", timeout=20).read()))
    try:
        d = fetch(name)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}"}
    uploads = {v: min((f.get("upload_time") or "9999")[:10] for f in files) for v, files in d.get("releases", {}).items() if files}
    stable = [v for v in uploads if not PRE.search(v)]
    pre = [v for v in uploads if PRE.search(v)]
    top = lambda vs: max(vs, key=version_key) if vs else None
    s, p = top(stable), top(pre)
    if p and s and version_key(p) <= version_key(s):
        p = None  # a pre-release older than the latest stable is not a newer line
    return {"stable": s, "stable_released": uploads.get(s), "prerelease": p, "prerelease_released": uploads.get(p)}


def status(installed: str, idx: dict) -> str:
    if "error" in idx or not idx.get("stable") and not idx.get("prerelease"):
        return "unknown"
    k, s = version_key(installed), idx.get("stable")
    if PRE.search(installed):
        p = idx.get("prerelease")
        if p and version_key(p) > k and (not s or version_key(p) > version_key(s)):
            return "prerelease_behind"
        return "prerelease_current" if not s or k > version_key(s) else "behind_stable"
    if s and k < version_key(s):
        return "behind_stable"
    return "current" if s and k == version_key(s) else "ahead_of_index"


def build(tools_dir: Path, host_label: str, watch=WATCH, runner=subprocess.run, fetch=None) -> dict:
    envs = {}
    for env in sorted(p for p in tools_dir.iterdir() if p.is_dir()):
        listed = list_env(env, runner)
        if listed is not None:
            envs[env.name] = listed
    names = sorted({n for e in envs.values() for n in e.get("dists", {}) if n in watch})
    with cf.ThreadPoolExecutor(8) as ex:
        index = dict(zip(names, ex.map(lambda n: pypi_latest(n, fetch), names)))
    rows = [{"env": env, "python": e.get("python"), "package": n, "installed": v, **{k: index[n].get(k) for k in
             ("stable", "stable_released", "prerelease", "prerelease_released")}, "status": status(v, index[n])}
            for env, e in envs.items() for n, v in sorted(e.get("dists", {}).items()) if n in index]
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {"schema_version": 1, "kind": "env_freshness", "host_label": host_label,
            "host": {"system": platform.system(), "release": platform.release(), "machine": platform.machine()},
            "checked_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "watch": list(watch),
            "environments": len(envs), "environment_errors": {k: v["error"] for k, v in envs.items() if "error" in v},
            "counts": counts, "rows": rows,
            "limits": "PyPI index only (a package installed from a git pin or another index reads as ahead_of_index or unknown); "
                      "CLIs and non-Python tools are covered by the catalog's GitHub freshness snapshot, not here; no adoption decision."}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tools-dir", type=Path, required=True)
    ap.add_argument("--host-label", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--offline-index", type=Path, help="JSON {package: PyPI JSON document} replayed instead of the network")
    a = ap.parse_args(argv)
    fetch = None
    if a.offline_index:
        docs = json.loads(a.offline_index.read_text())
        fetch = lambda n: docs[n]
    report = build(a.tools_dir.expanduser(), a.host_label, fetch=fetch)
    a.out.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"environments": report["environments"], "counts": report["counts"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
