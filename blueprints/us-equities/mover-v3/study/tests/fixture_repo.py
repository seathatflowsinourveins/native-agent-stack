"""A temporary git repository shaped like this one after the freeze (review round 9, F6): a committed study tree,
the data files, the cost table, a governing count-only output, and the protocol with status frozen in a commit on
origin/main. The CLI tests point run.REPO at it, so they never depend on the real protocol's status and never write
to the real run log. Every date and number is synthetic.
"""
from __future__ import annotations

import atexit
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
from core.canon import dumps, sha256_bytes, sha256_file, sha256_obj
from core.coverage_rule import rule_sha256
from core.params import (ACCESS_LOG, COST_TABLE, COUNT_ONLY_OUTPUT, DATA_DIR, DATA_PINS, PARAMETERS, PROTOCOL_PATH,
                         RESULTS_DIR, RUN_LOG, STUDY_PATH)

REAL = Path(__file__).resolve().parents[5]
# review round 15, N01: the fixture's fee file has data/fees-v3.json's schema (an open-ended last row included)
FEES_FIXTURE = {"schema_version": 1, "id": "synthetic-fees",
                "sec_section31": {"unit": "US dollars per million dollars of covered sales", "rows": [
                    {"from": "2016-01-01", "to": "2017-10-19", "usd_per_million": 21.80, "sources": []},
                    {"from": "2017-10-20", "to": None, "usd_per_million": 13.00, "sources": []}]},
                "finra_taf_covered_equity": {"unit": "US dollars per share sold, capped per trade", "rows": [
                    {"from": "2016-01-01", "to": None, "usd_per_share": 0.000119, "max_usd_per_trade": 5.95,
                     "sources": []}]}}


# Review round 10, M3: a synthetic merge key stands in for GitHub's web-flow key. It is generated once per test
# process in a temporary keyring, and core.guards.MERGE_KEY points at it for every test that imports this module;
# tests/test_guards.py verifies a real origin/main commit against the pinned key (guards.REAL_MERGE_KEY).
_KEY: dict = {}
PATH_ENV = os.environ.get("PATH", "/usr/bin:/bin")


def merge_key() -> dict:
    if not _KEY:
        from core import guards
        home = tempfile.mkdtemp(prefix="mover-v3-test-gnupg-")
        os.chmod(home, 0o700)
        (Path(home) / "gpg.conf").write_text("quiet\nno-greeting\ntrust-model always\n")
        env = {"GNUPGHOME": home, "PATH": PATH_ENV}
        subprocess.run(["gpg", "--batch", "--passphrase", "", "--quick-gen-key", "GitHub <noreply@github.com>",
                        "ed25519", "sign", "never"], env=env, check=True, capture_output=True)
        rows = subprocess.check_output(["gpg", "--batch", "--with-colons", "--list-secret-keys"], env=env, text=True)
        fpr = next(line.split(":")[9] for line in rows.splitlines() if line.startswith("fpr:"))
        pub = Path(home) / "merge-key.asc"
        pub.write_bytes(subprocess.check_output(["gpg", "--batch", "--armor", "--export", fpr], env=env))
        _KEY.update({"home": home, "fingerprint": fpr, "path": str(pub)})
        atexit.register(_drop_keyring, home)
        guards.MERGE_KEY = {"fingerprint": fpr, "committer_email": "noreply@github.com", "path": str(pub)}
    return _KEY


def _drop_keyring(home: str) -> None:
    subprocess.run(["gpgconf", "--homedir", home, "--kill", "all"], capture_output=True)
    shutil.rmtree(home, ignore_errors=True)


def sh(repo, *args, when: str | None = None, sign: bool = True, committer=("GitHub", "noreply@github.com")) -> str:
    key = merge_key()
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": committer[0],
           "GIT_COMMITTER_EMAIL": committer[1], "PATH": PATH_ENV, "HOME": str(repo), "GNUPGHOME": key["home"]}
    if when:
        env.update({"GIT_COMMITTER_DATE": when, "GIT_AUTHOR_DATE": when})
    pre = ["-c", "gpg.program=gpg", "-c", f"user.signingkey={key['fingerprint']}",
           "-c", f"commit.gpgsign={'true' if sign else 'false'}"]
    return subprocess.check_output(["git", "-C", str(repo), *pre, *args], text=True, env=env).strip()


def git_date(epoch: float) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def push(repo) -> str:
    """Push HEAD to the fixture's bare origin and fetch it back, so origin/main and the remote's main agree."""
    sh(repo, "push", "-q", "origin", "HEAD:main")
    sh(repo, "fetch", "-q", "origin")
    return sh(repo, "rev-parse", "HEAD")


def commit_push(repo, when: str, message: str = "run", sign: bool = True) -> str:
    """Commit everything, signed by the synthetic merge key, and push it (a merge that reached main at `when`)."""
    sh(repo, "add", "-A")
    if sh(repo, "status", "--porcelain"):
        sh(repo, "commit", "-q", "-m", message, when=when, sign=sign)
    return push(repo)


def init_repo(repo: Path) -> Path:
    """An empty repository with a bare origin beside it."""
    repo.mkdir(parents=True)
    origin = repo.parent / (repo.name + "-origin.git")
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    sh(repo, "init", "-q", "-b", "main")
    sh(repo, "remote", "add", "origin", str(origin))
    return repo


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


RATE_LIMIT = {"per_minute": 10000.0, "source": "synthetic"}


DATA_FILES = ("session-calendar.json", "fees-v3.json")


def count_only_output(protocol: dict, enumeration_sha256: str, dropped=(), tested=True, rate=0.01, deps=None) -> dict:
    """review round 15, F04: with the dependency manifest the freeze binds (runner.count_only_dependencies)."""
    return {"kind": "mover_v3_count_only_output", "coverage_rule_sha256": rule_sha256(protocol),
            "item_rule": {"items_tested": tested, "dropped_years": sorted(dropped)},
            "validation_identity_limited": rate > 0.02,
            "years": {"2020": {"rates": {"identity_unreached_rate": rate}}},
            "part0": {"enumeration_sha256": enumeration_sha256},
            "identity_probe": {"passes": True}, "fetch_margin": {"passes": True}, "rate_limit": dict(RATE_LIMIT),
            **({"study_tree": deps["study_tree"], "dependencies": deps} if deps else {})}


def count_only_line(deps: dict, output_sha256: str, protocol: dict) -> dict:
    """The complete 'count_only' run-log line that produced the output (review round 15, F04 and N02)."""
    return {"utc_start": "2026-09-30T12:30:00Z", "utc_end": "2026-09-30T12:40:00Z", "stage": "pre_freeze",
            "purpose": "count_only", "commit": "fixture", "study_tree": deps["study_tree"],
            "runtime_lock_sha256": deps["runtime_lock_sha256"], "protocol_sha256": "fixture-draft",
            "data_file_sha256s": deps["data_file_sha256s"], "amendment_files": {}, "input_snapshot_sha256s": [],
            "status": "complete", "results_sha256": output_sha256, "coverage_rule_sha256": rule_sha256(protocol),
            "output_path": COUNT_ONLY_OUTPUT, "start_index": None, "sealed_parts": ["part0", "part1", "part3"]}


def build(tmp, *, enumeration: dict | None = None, freeze_when: str = "2026-10-02T21:30:00+00:00",
          cal_first: str = "2015-09-01", cal_last: str = "2028-12-29", frozen: bool = True,
          coverage_decision=None, output_overrides: dict | None = None, freeze_sign: bool = True,
          with_count_only_line: bool = True) -> dict:
    """Returns {"repo", "enumeration" (path), "protocol" (parsed frozen), "tree"}."""
    repo = init_repo(Path(tmp) / "repo")
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
    data = {n: sha256_file(repo / DATA_DIR / n) for n in DATA_FILES}
    write(repo / DATA_PINS, json.dumps({"base_files": [{"path": f"{DATA_DIR}/{n}", "sha256": data[n]}
                                                      for n in DATA_FILES]}, indent=1) + "\n")
    write(repo / PROTOCOL_PATH, json.dumps(protocol, indent=1) + "\n")
    commit_push(repo, "2026-09-30T12:00:00+00:00", "study tree and draft protocol")
    tree = sh(repo, "rev-parse", f"HEAD:{STUDY_PATH}")
    # review round 15, F04: the governing count-only output names its dependencies, and its complete run-log line cites
    # it; both are bound to the tree, the data files and the specification the freeze pins
    deps = {"study_tree": tree, "runtime_lock_sha256": sha256_file(study / "runtime.lock"),
            "data_file_sha256s": dict(sorted(data.items())), "parameters_sha256": sha256_obj(PARAMETERS),
            "coverage_rule_sha256": rule_sha256(protocol), "rate_limit": {**RATE_LIMIT}}
    out = count_only_output(protocol, sha256_file(enum_path), deps=deps)
    out.update(output_overrides or {})
    write(repo / COUNT_ONLY_OUTPUT, json.dumps(out, sort_keys=True, indent=1) + "\n")
    if frozen and with_count_only_line:    # a draft fixture keeps an empty run log (pre-freeze command tests)
        write(repo / RUN_LOG, dumps(count_only_line(deps, sha256_file(repo / COUNT_ONLY_OUTPUT), protocol)) + "\n")
    commit_push(repo, "2026-09-30T13:00:00+00:00", "count-only output")
    if frozen:
        protocol["status"] = "frozen"
        protocol["frozen_before_outcomes"] = True
        # review round 14: a freeze that would allow a holdout count has an empty open list (core.holdout.authorize)
        protocol["open_before_first_holdout_count"] = []
        protocol["exposure_registry"]["pre_freeze_access_path"]["rate_limit"].update(RATE_LIMIT)
        sc = protocol["run_discipline"]["study_code"]
        sc["tree"] = tree
        sc["fetch_tree"] = sh(repo, "rev-parse", f"HEAD:{STUDY_PATH}/fetch")
        sc["data_file_sha256s"] = {n: sha256_file(repo / DATA_DIR / n) for n in ("session-calendar.json",
                                                                                   "fees-v3.json")}
        protocol["coverage_decision"] = coverage_decision if coverage_decision is not None else {
            "dropped_years": [], "items_tested": True, "count_only_output": COUNT_ONLY_OUTPUT,
            "count_only_output_sha256": sha256_file(repo / COUNT_ONLY_OUTPUT)}
        write(repo / PROTOCOL_PATH, json.dumps(protocol, indent=1) + "\n")
        commit_push(repo, freeze_when, "freeze", sign=freeze_sign)
    (repo / RESULTS_DIR).mkdir(parents=True, exist_ok=True)
    return {"repo": repo, "enumeration": enum_path, "protocol": protocol, "tree": tree,
            "protocol_sha256": sha256_bytes((repo / PROTOCOL_PATH).read_bytes())}


merge_key()
