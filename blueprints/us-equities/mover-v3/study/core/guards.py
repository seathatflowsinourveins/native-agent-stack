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

Review round 10: the local origin/main must equal the remote's main (require_remote_main, H2); every append-only file
must only have grown across origin/main's first-parent history (check_append_only_history, M1); a freeze or reach
time comes only from a commit signed by the pinned GitHub web-flow key (verified_merge, M3); a transport deviation
governs only with the hashed output of a logged run.py transport-check run (check_study_tree, H1); void deviations
are typed (voids, F4); and every locked package's version and dist-info RECORD digest is checked (check_runtime, L3).
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
# Review round 10, M3: the key GitHub signs its web-flow (squash-merge) commits with. Its public key block is pinned
# in the study tree (pinned/github-web-flow.gpg, fetched from https://github.com/web-flow.gpg on 2026-09-24); a
# reach, freeze or validation time is taken only from a commit whose signature verifies against it.
MERGE_KEY = {"fingerprint": "968479A1AFF927E37D1A566BB5690EEEBB952194",
             "committer_email": "noreply@github.com",
             "path": str(Path(__file__).resolve().parents[1] / "pinned" / "github-web-flow.gpg")}
REAL_MERGE_KEY = dict(MERGE_KEY)


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


# ---------------------------------------------------------------- verified merge commits (review round 10, M3)

_GNUPG_HOMES: dict = {}
_VERIFIED: dict = {}


def _gnupg_home(key: dict) -> str:
    """A private keyring holding only the pinned public key (created once per process and key file)."""
    import tempfile
    path = key["path"]
    if path not in _GNUPG_HOMES:
        home = tempfile.mkdtemp(prefix="mover-v3-gnupg-")
        subprocess.run(["gpg", "--batch", "--quiet", "--homedir", home, "--import", path], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _GNUPG_HOMES[path] = home
        import atexit
        import shutil
        atexit.register(lambda: (subprocess.run(["gpgconf", "--homedir", home, "--kill", "all"], capture_output=True),
                                 shutil.rmtree(home, ignore_errors=True)))
    return _GNUPG_HOMES[path]


def verified_merge(repo, commit: str, key: dict | None = None) -> bool:
    """True if the commit is signed by the pinned merge key (a VALIDSIG whose primary-key fingerprint is the pinned
    one) and its committer is the key's identity. The signature covers the committer line, so the committer time of
    such a commit is the time GitHub recorded when it merged, not one the client chose."""
    key = key or MERGE_KEY
    cache = (str(repo), commit, key["fingerprint"], key["path"])
    if cache in _VERIFIED:
        return _VERIFIED[cache]
    ok = False
    email = git(repo, "show", "-s", "--format=%ce", commit)
    if email == key["committer_email"]:
        env = {"GNUPGHOME": _gnupg_home(key), "PATH": __import__("os").environ.get("PATH", "/usr/bin:/bin")}
        res = subprocess.run(["git", "-C", str(repo), "-c", "gpg.program=gpg", "verify-commit", "--raw", commit],
                             capture_output=True, text=True, env=env)
        for line in res.stderr.splitlines():
            parts = line.split()
            if res.returncode == 0 and parts[:2] == ["[GNUPG:]", "VALIDSIG"] and \
                    parts[-1].upper() == key["fingerprint"].upper():
                ok = True
    _VERIFIED[cache] = ok
    return ok


def require_verified(repo, commit: str, what: str) -> None:
    if not verified_merge(repo, commit):
        raise Refused(f"{what}: commit {commit[:12]} is not a merge commit signed by the pinned merge key, so its "
                      "committer time is not a recorded reach time")


def commit_time(repo, commit: str) -> int:
    return int(git(repo, "show", "-s", "--format=%ct", commit))


def require_remote_main(repo, ref: str = MAIN) -> None:
    """The local origin/main equals the remote's main now (git ls-remote), so a locally moved tracking ref cannot
    stand in for a push (review round 10, H2)."""
    rows = git(repo, "ls-remote", "origin", "refs/heads/main").split()
    if not rows or rows[0] != git(repo, "rev-parse", ref):
        raise Refused("origin/main differs from the remote's main: fetch it, and push every line before a run")


def check_append_only_history(repo, paths, deviations_path: str = DEVIATIONS, ref: str = MAIN) -> None:
    """Every version of each append-only file on the first-parent history of origin/main is a byte prefix of the
    next (deviations.json: its deviations list is a prefix of the next), and none is deleted (review round 10, M1)."""
    for p in paths:
        rows = git(repo, "log", "--first-parent", "--reverse", "--format=%H", ref, "--", p).splitlines()
        prev = None
        for commit in rows:
            cur = committed_bytes(repo, commit, p)
            if prev is not None:
                if cur is None:
                    raise Refused(f"{p}: deleted at {commit[:12]}; an append-only file is never removed")
                if p == deviations_path:
                    a = json.loads(prev).get("deviations", [])
                    b = json.loads(cur).get("deviations", [])
                    grew = b[:len(a)] == a
                else:
                    grew = cur[:len(prev)] == prev
                if not grew:
                    raise Refused(f"{p}: edited, not appended, at {commit[:12]} on origin/main")
            prev = cur


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
            require_verified(repo, commit, "the freeze commit")    # review round 10, M3
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


VOID_SCOPES = ("tests", "validation", "holdout")


def voids(repo) -> frozenset:
    """exposure_registry.update_rule (review round 10, F4): the scopes of every committed 'void' deviation. 'tests'
    (a recorded pre-freeze read of v3-window data) and 'validation' (a pre-freeze read of a validation-window outcome)
    give every item p = 1 in the validation Holm run; 'holdout' (a holdout-window read before the gate opened) voids
    the holdout. Review round 13, F1: a 'holdout' void also cites the time of the read it records (read_utc). Whether
    a committed void applies is decided by its signed reach time (core.runner.void_effect)."""
    from core.calendar import parse_utc
    out = set()
    for dev in load_deviations(repo):
        if dev.get("kind") != "void":
            continue
        if dev.get("scope") not in VOID_SCOPES or not dev.get("cause"):
            raise Refused(f"a void deviation needs a scope in {VOID_SCOPES} and a cause: {dev.get('number')}")
        if dev["scope"] == "holdout":
            read_utc = dev.get("read_utc")
            try:
                if not isinstance(read_utc, str) or not read_utc.endswith("Z"):
                    raise ValueError(read_utc)
                parse_utc(read_utc)
            except ValueError:
                raise Refused(f"a 'holdout' void deviation cites the time of the read it records (read_utc): "
                              f"{dev.get('number')}") from None
        out.add(dev["scope"])
    return frozenset(out)


def void_records(repo, ref: str = None) -> list:
    """Review round 13, F1: [(deviation, signed reach epoch)] for every 'void' deviation on origin/main, in order:
    the committer time of the first first-parent commit whose deviations.json holds a void record with that number
    (the file is append-only, check_append_only_history)."""
    ref = ref or MAIN
    out, seen = [], set()
    for row in git(repo, "log", "--first-parent", "--reverse", "--format=%H %ct", ref, "--", DEVIATIONS).splitlines():
        commit, ct = row.split()
        raw = committed_bytes(repo, commit, DEVIATIONS)
        try:
            devs = json.loads(raw).get("deviations", []) if raw else []
        except ValueError:
            continue
        new = [d for d in devs if d.get("kind") == "void" and d.get("scope") in VOID_SCOPES
               and json.dumps(d.get("number")) not in seen]
        if new:
            require_verified(repo, commit, "the first commit holding a void deviation")
            for d in new:
                seen.add(json.dumps(d.get("number")))
                out.append((d, int(ct)))
    return out


def first_reach(repo, path: str, ref: str = None):
    """Committer epoch of the first first-parent commit of origin/main that holds path, or None."""
    for row in git(repo, "log", "--first-parent", "--reverse", "--format=%H %ct", ref or MAIN, "--", path).splitlines():
        commit, ct = row.split()
        if committed_bytes(repo, commit, path) is not None:
            require_verified(repo, commit, f"the first commit holding {path}")
            return int(ct)
    return None


def fetch_only_diff(repo, pinned: str, tree: str) -> bool:
    """The running tree differs from the pinned tree, and only in paths under fetch/."""
    if not pinned or not git_ok(repo, "cat-file", "-e", f"{pinned}^{{tree}}"):
        return False
    changed = git(repo, "diff-tree", "-r", "--name-only", pinned, tree).splitlines()
    return bool(changed) and all(p.startswith("fetch/") for p in changed)


def transport_check_output(repo, tree: str, run_log: list, output_path: str | None, output_sha256: str | None):
    """The committed reproduction-check output for this tree, or None: the file at output_path has the recorded
    sha256, says passes for this new tree, and a complete 'transport_check' run-log line from this tree wrote it
    (run.py transport-check; review round 10, H1 and F6)."""
    from core.params import RESULTS_DIR
    if not output_path or not output_sha256 or not output_path.startswith(RESULTS_DIR + "/"):
        return None
    f = Path(repo) / output_path
    if not f.exists() or sha256_bytes(f.read_bytes()) != output_sha256:
        return None
    body = json.loads(f.read_text(encoding="utf-8"))
    if body.get("new_tree") != tree or body.get("passes") is not True:
        return None
    logged = any(x.get("purpose") == "transport_check" and x.get("status") == "complete" and
                 x.get("results_sha256") == output_sha256 and x.get("study_tree") == tree for x in run_log)
    return body if logged else None


def check_study_tree(repo, protocol: dict, tree: str, run_log: list | None = None):
    """None if the running tree is the pinned tree. Otherwise the committed transport deviation that governs it:
    deviations.json holds a 'transport' entry whose new_tree is the running tree, whose new_fetch_tree is the running
    study/fetch/ tree, and whose transport_check names the committed output of a logged run.py transport-check run
    from that tree that passed (output_path and output_sha256; review round 10, H1); and the running tree differs
    from the pinned tree only under study/fetch/ (run_discipline.transport_deviations; review round 9, H-2). A
    self-declared passes: true without that output is refused. Any other tree is refused."""
    sc = protocol.get("run_discipline", {}).get("study_code") or {}
    pinned = sc.get("tree")
    if tree == pinned:
        return None
    fetch_tree = git(repo, "rev-parse", f"HEAD:{STUDY_PATH}/fetch")
    for dev in load_deviations(repo):
        if dev.get("kind") != "transport" or dev.get("new_tree") != tree or dev.get("new_fetch_tree") != fetch_tree:
            continue
        tc = dev.get("transport_check") or {}
        if tc.get("passes") is not True or transport_check_output(
                repo, tree, run_log or [], tc.get("output_path"), tc.get("output_sha256")) is None:
            continue
        if fetch_only_diff(repo, pinned, tree):
            return dev
    raise Refused(f"running study tree {tree} is not the frozen study_code.tree {pinned} or a passing transport "
                  "deviation of it")


def first_commit_with_tree(repo, tree: str, path: str = STUDY_PATH):
    """The id of the first first-parent commit of origin/main whose `path` tree is `tree`, or None (review round 11,
    F3: the transport-check sample seed)."""
    for commit in git(repo, "log", "--first-parent", "--reverse", "--format=%H", MAIN, "--", path).splitlines():
        if git_ok(repo, "rev-parse", "-q", "--verify", f"{commit}:{path}") and \
                git(repo, "rev-parse", f"{commit}:{path}") == tree:
            return commit
    return None


def check_parameters(protocol: dict) -> None:
    got = (protocol.get("run_discipline", {}).get("study_code") or {}).get("parameters")
    if got != PARAMETERS:
        raise Refused("run_discipline.study_code.parameters differs from the code's parameters")
    # review round 15, amendment format: the line schema the code validates is the protocol's
    from core.amendments import FORMAT
    if protocol.get("run_discipline", {}).get("amendment_format") != FORMAT:
        raise Refused("run_discipline.amendment_format differs from the code's amendment line schema")


# ---------------------------------------------------------------- runtime and vintages

def runtime_versions(lock: dict | None = None) -> dict:
    """The Python version and the installed version of every package runtime.lock lists (review round 10, L3; the
    four imported packages when no lock is given)."""
    import importlib.metadata as md
    names = list((lock or {}).get("packages") or ALLOWED_THIRD_PARTY)
    out = {"python": ".".join(map(str, sys.version_info[:3]))}
    for n in names:
        try:
            out[n] = md.version(n)
        except md.PackageNotFoundError:
            out[n] = None
    return out


def record_digests(lock: dict) -> dict:
    """{package: sha256 of its installed dist-info RECORD}, which lists the sha256 of every installed file."""
    import importlib.metadata as md
    out = {}
    for n in lock["packages"]:
        try:
            rec = next((f for f in md.distribution(n).files or () if f.name == "RECORD"), None)
            out[n] = sha256_bytes(Path(rec.locate()).read_bytes()) if rec is not None else None
        except md.PackageNotFoundError:
            out[n] = None
    return out


def environment_digest(lock: dict) -> str:
    """The sha256 of the RECORD digests and of every .pth file in the interpreter's site directories; the run-log
    line records it (review round 10, L3: python -I does not stop a .pth file from running, so its bytes are
    recorded)."""
    import glob
    import site
    pth = {}
    for d in sorted(set(site.getsitepackages() + [site.getusersitepackages()])):
        for f in sorted(glob.glob(str(Path(d) / "*.pth"))):
            pth[f"{Path(f).name}"] = sha256_bytes(Path(f).read_bytes())
    return sha256_bytes(json.dumps({"records": record_digests(lock), "pth": pth}, sort_keys=True).encode("utf-8"))


def load_lock(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def check_runtime(lock: dict, versions: dict | None = None, records: dict | None = None) -> None:
    """Refuses a Python or package version other than runtime.lock's, for every locked package, and an installed
    distribution whose RECORD differs from the lock's record_sha256s (review round 10, L3)."""
    versions = versions or runtime_versions(lock)
    want = {"python": lock["python"], **lock["packages"]}
    diff = {k: (versions.get(k), v) for k, v in want.items() if versions.get(k) != v}
    if diff:
        raise Refused(f"runtime differs from study/runtime.lock: {diff}")
    pinned = lock.get("record_sha256s")
    if pinned:
        records = records or record_digests(lock)
        bad = sorted(k for k, v in pinned.items() if records.get(k) != v)
        if bad:
            raise Refused(f"installed distributions differ from study/runtime.lock record_sha256s: {bad}")


def check_vintages(vintages: list, freeze_utc: str) -> None:
    """A development, validation, count or read snapshot page fetched before the freeze commit is refused."""
    early = [v for v in vintages if v < freeze_utc]
    if early:
        raise Refused(f"{len(early)} snapshot vintages precede the freeze commit time")
