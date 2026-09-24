"""Refusals that run before any fetch or evaluation (run_discipline, holdout_gate.evaluator_refusals).

Review round 8, R8-4: every fetch and evaluation entry point refuses unless the protocol file at its fixed path
has status frozen and its study_code.tree equals the tree actually running, and a development, validation, count
or read snapshot refuses any page whose vintage precedes the freeze commit time (pre-freeze parts 0, 1 and 3 are
opened only by the count-only code). R8-2: the protocol sha256 must equal the freeze commit's blob and the
parameters object must equal core.params.PARAMETERS.

Review round 9: the protocol that runs is the freeze commit's blob, and the working copy and HEAD must equal it
(F3); every log, amendment and deviation file must equal its origin/main content, and HEAD must be reachable from
origin/main (F2); a tree that differs from the pinned tree only under study/fetch/ runs only under a committed
passing transport deviation (H-2); no ignored file other than a __pycache__ entry may sit in the study tree, and
the entry point reads no bytecode cache from the tree (F9).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from core.canon import sha256_bytes
from core.params import DEVIATIONS, PARAMETERS, PROTOCOL_PATH, STUDY_PATH

ALLOWED_THIRD_PARTY = ("numpy", "pandas", "exchange_calendars", "duckdb")
MAIN = "origin/main"


class Refused(Exception):
    pass


def git(repo, *args) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def git_ok(repo, *args) -> bool:
    return subprocess.run(["git", "-C", str(repo), *args], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0


def committed_bytes(repo, ref: str, path: str):
    """The bytes of path at ref, or None if the path does not exist there."""
    if not git_ok(repo, "cat-file", "-e", f"{ref}:{path}"):
        return None
    return subprocess.check_output(["git", "-C", str(repo), "show", f"{ref}:{path}"])


# ---------------------------------------------------------------- the running tree

def running_tree(repo, study_path: str = STUDY_PATH) -> str:
    """The git tree hash of the study directory at HEAD; refuses if the working copy of it differs from HEAD, or
    if it holds an ignored file other than a __pycache__ entry (review round 9, F9: an ignored file is invisible to
    the tree hash but could still be imported)."""
    dirty = git(repo, "status", "--porcelain", "--untracked-files=all", "--", study_path)
    if dirty:
        raise Refused("the study tree has uncommitted changes; a run executes a committed tree only")
    ignored = [line[3:] for line in git(repo, "status", "--porcelain", "--ignored", "--untracked-files=all", "--",
                                        study_path).splitlines() if line.startswith("!! ")]
    planted = [p for p in ignored if "__pycache__" not in Path(p).parts]
    if planted:
        raise Refused(f"the study tree holds ignored files that are not bytecode caches: {planted[:5]}")
    return git(repo, "rev-parse", f"HEAD:{study_path}")


def check_bytecode_isolated() -> None:
    """run.py sets sys.pycache_prefix to a fresh directory and turns bytecode writing off before it imports any study
    module, so a __pycache__ file in the tree is never read (review round 9, F9)."""
    if not sys.pycache_prefix or not sys.dont_write_bytecode:
        raise Refused("run through run.py: it reads no bytecode cache from the study tree")


def require_on_main(repo, paths, ref: str = MAIN) -> None:
    """HEAD is reachable from origin/main, and every listed append-only file equals its origin/main content, so every
    earlier line is committed and pushed before this run starts (review round 9, F2)."""
    head = git(repo, "rev-parse", "HEAD")
    if not git_ok(repo, "merge-base", "--is-ancestor", head, ref):
        raise Refused("HEAD is not reachable from origin/main")
    for p in paths:
        local = Path(repo) / p
        have = local.read_bytes() if local.exists() else None
        if have != committed_bytes(repo, ref, p):
            raise Refused(f"{p} differs from origin/main: every earlier line is committed and pushed before a run")


# ---------------------------------------------------------------- the frozen protocol

def freeze_commit(repo, ref: str = MAIN):
    """(commit, committer epoch): the first commit on the first-parent history of origin/main in which the protocol
    file has status frozen (chronology.holdout.window)."""
    rows = git(repo, "log", "--first-parent", "--reverse", "--format=%H %ct", ref, "--", PROTOCOL_PATH).splitlines()
    for row in rows:
        commit, ct = row.split()
        body = json.loads(git(repo, "show", f"{commit}:{PROTOCOL_PATH}"))
        if body.get("status") == "frozen":
            return commit, int(ct)
    raise Refused("no frozen protocol commit on origin/main")


def freeze_commit_utc(repo, ref: str = MAIN) -> str:
    from datetime import datetime, timezone
    _, ct = freeze_commit(repo, ref)
    return datetime.fromtimestamp(ct, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def check_protocol_sha(protocol_bytes: bytes, frozen_sha256: str) -> None:
    if sha256_bytes(protocol_bytes) != frozen_sha256:
        raise Refused("the protocol sha256 differs from the frozen commit's blob")


def frozen_protocol(repo, commit: str):
    """(bytes, parsed) of the protocol at the freeze commit. The working copy and HEAD must hold the same bytes, so an
    edit of id, coverage_decision or data_file_sha256s after the freeze cannot reach a run (review round 9, F3)."""
    frozen = committed_bytes(repo, commit, PROTOCOL_PATH)
    want = sha256_bytes(frozen)
    check_protocol_sha((Path(repo) / PROTOCOL_PATH).read_bytes(), want)
    check_protocol_sha(committed_bytes(repo, "HEAD", PROTOCOL_PATH) or b"", want)
    return frozen, json.loads(frozen)


def require_frozen(protocol: dict, tree: str | None = None) -> None:
    if protocol.get("status") != "frozen" or protocol.get("frozen_before_outcomes") is not True:
        raise Refused("the protocol status is not frozen: no fetch or evaluation may run (count-only code excepted)")
    if tree is not None:
        pinned = (protocol.get("run_discipline", {}).get("study_code") or {}).get("tree")
        if pinned != tree:
            raise Refused(f"running study tree {tree} is not the frozen study_code.tree {pinned}")


def load_deviations(repo) -> list:
    p = Path(repo) / DEVIATIONS
    if not p.exists():
        return []
    return list(json.loads(p.read_text(encoding="utf-8")).get("deviations", []))


def check_study_tree(repo, protocol: dict, tree: str):
    """None if the running tree is the pinned tree. Otherwise the committed transport deviation that governs it:
    deviations.json holds a 'transport' entry whose new_tree is the running tree, whose new_fetch_tree is the running
    study/fetch/ tree and whose transport_check passed, and the running tree differs from the pinned tree only under
    study/fetch/ (run_discipline.transport_deviations; review round 9, H-2). Any other tree is refused."""
    sc = protocol.get("run_discipline", {}).get("study_code") or {}
    pinned = sc.get("tree")
    if tree == pinned:
        return None
    fetch_tree = git(repo, "rev-parse", f"HEAD:{STUDY_PATH}/fetch")
    for dev in load_deviations(repo):
        if dev.get("kind") != "transport" or dev.get("new_tree") != tree:
            continue
        if dev.get("new_fetch_tree") != fetch_tree or (dev.get("transport_check") or {}).get("passes") is not True:
            continue
        if not pinned or not git_ok(repo, "cat-file", "-e", f"{pinned}^{{tree}}"):
            break
        changed = git(repo, "diff-tree", "-r", "--name-only", pinned, tree).splitlines()
        if changed and all(p.startswith("fetch/") for p in changed):
            return dev
    raise Refused(f"running study tree {tree} is not the frozen study_code.tree {pinned} or a passing transport "
                  "deviation of it")


def check_parameters(protocol: dict) -> None:
    got = (protocol.get("run_discipline", {}).get("study_code") or {}).get("parameters")
    if got != PARAMETERS:
        raise Refused("run_discipline.study_code.parameters differs from the code's parameters")


# ---------------------------------------------------------------- runtime and vintages

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
