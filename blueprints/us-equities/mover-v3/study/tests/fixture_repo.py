"""A temporary git repository shaped like this one after the freeze (review round 9, F6): a committed study tree,
the data files, the cost table, a governing count-only output, and the protocol with status frozen in a commit on
origin/main. The CLI tests point run.REPO at it, so they never depend on the real protocol's status and never write
to the real run log. Every date and number is synthetic.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

from core.calendar import build_calendar
from core.canon import dumps, sha256_bytes, sha256_file
from core.coverage_rule import rule_sha256
from core.params import (ACCESS_LOG, COST_TABLE, COUNT_ONLY_OUTPUT, DATA_DIR, PROTOCOL_PATH, RESULTS_DIR, RUN_LOG,
                         STUDY_PATH)

REAL = Path(__file__).resolve().parents[5]
FEES_FIXTURE = {"sec_section31_usd_per_million_of_sales": [
    {"from": "2016-01-01", "to": "2017-10-19", "rate": 21.80, "source": "synthetic"},
    {"from": "2017-10-20", "to": "2028-12-31", "rate": 13.00, "source": "synthetic"}],
    "finra_taf_covered_equity_sales": [
    {"from": "2016-01-01", "to": "2028-12-31", "usd_per_share": 0.000119, "max_per_trade": 5.95, "source": "synthetic"}]}


def sh(repo, *args, when: str | None = None) -> str:
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.invalid", "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
           "HOME": str(repo)}
    if when:
        env.update({"GIT_COMMITTER_DATE": when, "GIT_AUTHOR_DATE": when})
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True, env=env).strip()


def git_date(epoch: float) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def commit_push(repo, when: str, message: str = "run") -> str:
    """Commit everything and move origin/main to it (a push that reached main at `when`)."""
    sh(repo, "add", "-A")
    if sh(repo, "status", "--porcelain"):
        sh(repo, "commit", "-q", "-m", message, when=when)
    sh(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    return sh(repo, "rev-parse", "HEAD")


@contextlib.contextmanager
def isolated_bytecode():
    """What run.py's __main__ block sets before it imports a study module (F9); run.py's stdout is discarded."""
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(sys, "pycache_prefix", tmp), \
            mock.patch.object(sys, "dont_write_bytecode", True), contextlib.redirect_stdout(io.StringIO()):
        yield


def write(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    return path


def count_only_output(protocol: dict, enumeration_sha256: str, dropped=(), tested=True, rate=0.01) -> dict:
    return {"kind": "mover_v3_count_only_output", "coverage_rule_sha256": rule_sha256(protocol),
            "item_rule": {"items_tested": tested, "dropped_years": sorted(dropped)},
            "validation_identity_limited": rate > 0.02,
            "years": {"2020": {"rates": {"identity_unreached_rate": rate}}},
            "part0": {"enumeration_sha256": enumeration_sha256}}


def build(tmp, *, enumeration: dict | None = None, freeze_when: str = "2026-10-02T21:30:00+00:00",
          cal_first: str = "2015-09-01", cal_last: str = "2028-12-29", frozen: bool = True,
          coverage_decision=None, output_overrides: dict | None = None) -> dict:
    """Returns {"repo", "enumeration" (path), "protocol" (parsed frozen), "tree"}."""
    repo = Path(tmp) / "repo"
    repo.mkdir()
    sh(repo, "init", "-q", "-b", "main")
    write(repo / ".gitignore", (REAL / ".gitignore").read_text())
    study = repo / STUDY_PATH
    write(study / "core" / "__init__.py", "# fixture\n")
    write(study / "fetch" / "transport.py", "HOST = 'fixture'\n")
    shutil.copy(REAL / STUDY_PATH / "runtime.lock", study / "runtime.lock")
    write(repo / DATA_DIR / "session-calendar.json", json.dumps(build_calendar(cal_first, cal_last)))
    write(repo / DATA_DIR / "fees-v3.json", json.dumps(FEES_FIXTURE))
    for n in ("session-calendar-amendments.jsonl", "fees-v3-amendments.jsonl"):
        write(repo / DATA_DIR / n, "")
    write(repo / COST_TABLE["path"], (REAL / COST_TABLE["path"]).read_bytes())
    for p in (RUN_LOG, ACCESS_LOG):
        write(repo / p, "")
    enum = enumeration or {"symbols": [], "actions": [], "active": [], "counts": {}}
    enum_path = write(Path(tmp) / "enumeration.json", dumps(enum) + "\n")
    protocol = json.loads((REAL / PROTOCOL_PATH).read_text())
    out = count_only_output(protocol, sha256_file(enum_path))
    out.update(output_overrides or {})
    write(repo / COUNT_ONLY_OUTPUT, json.dumps(out, sort_keys=True, indent=1) + "\n")
    write(repo / PROTOCOL_PATH, json.dumps(protocol, indent=1) + "\n")
    commit_push(repo, "2026-09-30T12:00:00+00:00", "study tree and draft protocol")
    tree = sh(repo, "rev-parse", f"HEAD:{STUDY_PATH}")
    if frozen:
        protocol["status"] = "frozen"
        protocol["frozen_before_outcomes"] = True
        sc = protocol["run_discipline"]["study_code"]
        sc["tree"] = tree
        sc["fetch_tree"] = sh(repo, "rev-parse", f"HEAD:{STUDY_PATH}/fetch")
        sc["data_file_sha256s"] = {n: sha256_file(repo / DATA_DIR / n) for n in ("session-calendar.json",
                                                                                   "fees-v3.json")}
        protocol["coverage_decision"] = coverage_decision if coverage_decision is not None else {
            "dropped_years": [], "items_tested": True, "count_only_output": COUNT_ONLY_OUTPUT,
            "count_only_output_sha256": sha256_file(repo / COUNT_ONLY_OUTPUT)}
        write(repo / PROTOCOL_PATH, json.dumps(protocol, indent=1) + "\n")
        commit_push(repo, freeze_when, "freeze")
    (repo / RESULTS_DIR).mkdir(parents=True, exist_ok=True)
    return {"repo": repo, "enumeration": enum_path, "protocol": protocol, "tree": tree,
            "protocol_sha256": sha256_bytes((repo / PROTOCOL_PATH).read_bytes())}
