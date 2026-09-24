"""Refusals that run before any fetch or evaluation (run_discipline, holdout_gate.evaluator_refusals).

Review round 8, R8-4: every fetch and evaluation entry point refuses unless the protocol file at its fixed path
has status frozen and its study_code.tree equals the tree actually running, and a development, validation, count
or read snapshot refuses any page whose vintage precedes the freeze commit time (pre-freeze parts 0, 1 and 3 are
opened only by the count-only code). R8-2: the protocol sha256 must equal the freeze commit's blob and the
parameters object must equal core.params.PARAMETERS.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from core.canon import sha256_bytes
from core.params import PARAMETERS, PROTOCOL_PATH, STUDY_PATH

ALLOWED_THIRD_PARTY = ("numpy", "pandas", "exchange_calendars", "duckdb")


class Refused(Exception):
    pass


def git(repo, *args) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def running_tree(repo, study_path: str = STUDY_PATH) -> str:
    """The git tree hash of the study directory at HEAD; refuses if the working copy of it differs from HEAD."""
    dirty = git(repo, "status", "--porcelain", "--untracked-files=all", "--", study_path)
    if dirty:
        raise Refused("the study tree has uncommitted changes; a run executes a committed tree only")
    return git(repo, "rev-parse", f"HEAD:{study_path}")


def require_frozen(protocol: dict, tree: str) -> None:
    if protocol.get("status") != "frozen" or protocol.get("frozen_before_outcomes") is not True:
        raise Refused("the protocol status is not frozen: no fetch or evaluation may run (count-only code excepted)")
    pinned = (protocol.get("run_discipline", {}).get("study_code") or {}).get("tree")
    if pinned != tree:
        raise Refused(f"running study tree {tree} is not the frozen study_code.tree {pinned}")


def check_protocol_sha(protocol_bytes: bytes, frozen_sha256: str) -> None:
    if sha256_bytes(protocol_bytes) != frozen_sha256:
        raise Refused("the protocol sha256 differs from the frozen commit's blob")


def check_parameters(protocol: dict) -> None:
    got = (protocol.get("run_discipline", {}).get("study_code") or {}).get("parameters")
    if got != PARAMETERS:
        raise Refused("run_discipline.study_code.parameters differs from the code's parameters")


def runtime_versions() -> dict:
    import duckdb
    import exchange_calendars
    import numpy
    import pandas
    return {"python": ".".join(map(str, sys.version_info[:3])), "numpy": numpy.__version__,
            "pandas": pandas.__version__, "exchange_calendars": exchange_calendars.__version__,
            "duckdb": duckdb.__version__}


def load_lock(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def check_runtime(lock: dict, versions: dict | None = None) -> None:
    versions = versions or runtime_versions()
    want = {"python": lock["python"], **{k: lock["packages"][k] for k in ("numpy", "pandas", "exchange_calendars",
                                                                           "duckdb")}}
    diff = {k: (versions.get(k), v) for k, v in want.items() if versions.get(k) != v}
    if diff:
        raise Refused(f"runtime differs from study/runtime.lock: {diff}")


def check_vintages(vintages: list, freeze_utc: str) -> None:
    """A development, validation, count or read snapshot page fetched before the freeze commit is refused."""
    early = [v for v in vintages if v < freeze_utc]
    if early:
        raise Refused(f"{len(early)} snapshot vintages precede the freeze commit time")


def freeze_commit_utc(repo, ref: str = "origin/main") -> str:
    """The freeze commit is the first commit on the first-parent history of origin/main in which the protocol file
    has status frozen; its committer time (UTC) is the freeze time (chronology.holdout.window)."""
    from datetime import datetime, timezone
    rows = git(repo, "log", "--first-parent", "--reverse", "--format=%H %ct", ref, "--", PROTOCOL_PATH).splitlines()
    for row in rows:
        commit, ct = row.split()
        body = json.loads(git(repo, "show", f"{commit}:{PROTOCOL_PATH}"))
        if body.get("status") == "frozen":
            return datetime.fromtimestamp(int(ct), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raise Refused("no frozen protocol commit on origin/main")
