"""Shared paths, loaders and the freeze guard for the ORB replication (stdlib only)."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PROTOCOL_PATH = HERE / "protocol.json"
FEES_PATH = REPO / "blueprints/us-equities/mover-v3/data/fees-v3.json"
CALENDAR_PATH = REPO / "blueprints/us-equities/mover-v3/data/session-calendar.json"
MINUTE_ROOT = Path.home() / ".local/share/native-agent-stack/minute-bars/stage1"
MINUTE_PLAN = MINUTE_ROOT / "minute-plan-stage1.json"
DAILY_PARQUET = Path.home() / "codex-ecosystem/state/broad-market-20260921/dataset/daily.parquet"
PRIVATE = Path.home() / ".local/state/native-agent-stack/research/sota-mover/orb"
FROZEN_STATUS = "frozen_before_outcomes"
FREEZE_RECORD = HERE / "evidence/freeze-record.json"
STUDY_DIR = HERE


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class FreezeError(SystemExit):
    pass


def require_frozen(protocol_path: Path, expected_sha256: str | None) -> dict:
    """Refuse unless the freeze record exists, --protocol-sha256 equals the sha256 it records, the protocol
    file hashes to that value and its status is frozen.

    The expected sha256 comes from the freeze record (FREEZE_RECORD, written at freeze time), never from
    the working protocol file. Called before any outcome (price after a decision time) is read."""
    if not expected_sha256:
        raise FreezeError("refused: --protocol-sha256 is required before any outcome is computed")
    rec_path = Path(FREEZE_RECORD)
    if not rec_path.exists():
        raise FreezeError("refused: no freeze record (evidence/freeze-record.json)")
    recorded = str(json.loads(rec_path.read_text()).get("protocol_sha256", "")).strip().lower()
    if not recorded or expected_sha256.strip().lower() != recorded:
        raise FreezeError("refused: --protocol-sha256 does not match the freeze record")
    raw = Path(protocol_path).read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != recorded:
        raise FreezeError(f"refused: protocol sha256 {actual} does not match the freeze record")
    proto = json.loads(raw)
    if proto.get("status") != FROZEN_STATUS or proto.get("frozen_before_outcomes") is not True:
        raise FreezeError(f"refused: protocol status is {proto.get('status')!r}, not {FROZEN_STATUS!r} "
                          "with frozen_before_outcomes true")
    return proto


def git_state(study_dir: Path):
    """(HEAD sha, [porcelain lines for the study directory]) or (None, None) outside a git work tree."""
    try:
        head = subprocess.run(["git", "-C", str(study_dir), "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(study_dir), "status", "--porcelain", "--untracked-files=all",
                                "--", "."], capture_output=True, text=True, check=True).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        return None, None
    return head, dirty


def require_clean_tree(study_dir: Path | None = None) -> str:
    """Refuse on a dirty (or missing) git tree for the study directory; return HEAD for the record."""
    head, dirty = git_state(Path(study_dir or STUDY_DIR))
    if head is None:
        raise FreezeError("refused: the study directory is not in a git work tree")
    if dirty:
        raise FreezeError(f"refused: the study directory has {len(dirty)} uncommitted change(s)")
    return head


def _git(study_dir: Path, *args, binary: bool = False):
    return subprocess.run(["git", "-C", str(study_dir), *args], capture_output=True, text=not binary)


def require_freeze_commit(study_dir: Path | None = None) -> str:
    """Bind the code to the freeze: refuse unless the freeze record's `protocol_commit` (40 hex) is an
    ancestor of HEAD, protocol.json at that commit hashes to the recorded `protocol_sha256`, and nothing in
    the study directory other than evidence/ changed between that commit and HEAD. Returns the commit."""
    study = Path(study_dir or STUDY_DIR)
    rec_path = Path(FREEZE_RECORD)
    if not rec_path.exists():
        raise FreezeError("refused: no freeze record (evidence/freeze-record.json)")
    rec = json.loads(rec_path.read_text())
    commit = str(rec.get("protocol_commit", "")).strip().lower()
    recorded = str(rec.get("protocol_sha256", "")).strip().lower()
    if len(commit) != 40 or any(ch not in "0123456789abcdef" for ch in commit):
        raise FreezeError("refused: the freeze record has no 40-hex protocol_commit")
    if _git(study, "merge-base", "--is-ancestor", commit, "HEAD").returncode != 0:
        raise FreezeError("refused: protocol_commit is not an ancestor of HEAD")
    shown = _git(study, "show", f"{commit}:./protocol.json", binary=True)
    if shown.returncode != 0 or hashlib.sha256(shown.stdout).hexdigest() != recorded:
        raise FreezeError("refused: protocol.json at protocol_commit does not hash to the recorded protocol_sha256")
    diff = _git(study, "diff", "--name-only", "--relative", commit, "HEAD", "--", ".")
    if diff.returncode != 0:
        raise FreezeError("refused: cannot diff protocol_commit against HEAD")
    changed = [p for p in diff.stdout.splitlines() if p and not p.startswith("evidence/")]
    if changed:
        raise FreezeError(f"refused: {len(changed)} study file(s) changed after the freeze commit, e.g. {changed[0]}")
    return commit


def input_paths() -> dict:
    """Pinned external inputs by name (resolved at call time)."""
    return {"daily_parquet": DAILY_PARQUET, "minute_plan": MINUTE_PLAN, "fees": FEES_PATH, "calendar": CALENDAR_PATH}


def verify_pins(proto: dict) -> None:
    """Refuse when a private artifact or an external input differs from the sha256 the frozen protocol pins."""
    pins = proto.get("pinned_artifacts") or {}
    private, inputs = pins.get("private") or {}, pins.get("inputs") or {}
    if not private or set(inputs) != set(input_paths()):
        raise FreezeError("refused: the protocol does not pin every private artifact and external input")
    for name, sha in private.items():
        path = PRIVATE / name
        if not path.exists() or sha256_file(path) != sha:
            raise FreezeError(f"refused: private artifact {name} does not match its pinned sha256")
    paths = input_paths()
    for name, sha in inputs.items():
        path = Path(paths[name])
        if not path.exists() or sha256_file(path) != sha:
            raise FreezeError(f"refused: input {name} does not match its pinned sha256")


def check_trades(population: str, protocol_sha256: str) -> dict:
    """Refuse unless trades-<population>.csv.gz matches the sha256 in its counts file and that counts
    file records the same frozen protocol sha256."""
    counts_path = PRIVATE / f"trades-{population}.counts.json"
    trades_path = PRIVATE / f"trades-{population}.csv.gz"
    if not counts_path.exists() or not trades_path.exists():
        raise FreezeError(f"refused: trades-{population} or its counts file is missing")
    counts = json.loads(counts_path.read_text())
    if counts.get("protocol_sha256") != protocol_sha256.strip().lower():
        raise FreezeError(f"refused: trades-{population} was simulated under another protocol")
    if sha256_file(trades_path) != counts.get("sha256"):
        raise FreezeError(f"refused: trades-{population}.csv.gz does not match its counts file")
    return counts


def load_json(path: Path):
    return json.loads(Path(path).read_text())


def calendar():
    """[(session, close_minute)] for scheduled XNYS sessions (early closes at 13:00 -> 780)."""
    cal = load_json(CALENDAR_PATH)
    cols = cal["columns"]
    i_s, i_c = cols.index("session"), cols.index("close_et")
    out = []
    for row in cal["sessions"]:
        hh, mm = row[i_c][11:16].split(":")
        out.append((row[i_s], int(hh) * 60 + int(mm)))
    return out


def private_dir(*parts) -> Path:
    p = PRIVATE.joinpath(*parts)
    p.mkdir(parents=True, exist_ok=True, mode=0o700)
    return p


def write_private_json(path: Path, obj) -> str:
    body = (json.dumps(obj, indent=1, sort_keys=True) + "\n").encode()
    path.write_bytes(body)
    os.chmod(path, 0o600)
    return hashlib.sha256(body).hexdigest()
