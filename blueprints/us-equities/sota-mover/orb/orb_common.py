"""Shared paths, loaders and the freeze guard for the ORB replication (stdlib only)."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
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


def load_signal():
    """signal.py by path under a private module name (it shadows the stdlib ``signal``)."""
    name = "orb_signal"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, HERE / "signal.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class FreezeError(SystemExit):
    pass


def require_frozen(protocol_path: Path, expected_sha256: str | None) -> dict:
    """Refuse to go further unless the protocol is frozen and its bytes hash to the given sha256.

    Called before any outcome (price after a decision time) is read or computed on real data."""
    if not expected_sha256:
        raise FreezeError("refused: --protocol-sha256 is required before any outcome is computed")
    raw = Path(protocol_path).read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected_sha256.strip().lower():
        raise FreezeError(f"refused: protocol sha256 {actual} does not match --protocol-sha256")
    proto = json.loads(raw)
    if proto.get("status") != FROZEN_STATUS or proto.get("frozen_before_outcomes") is not True:
        raise FreezeError(f"refused: protocol status is {proto.get('status')!r}, not {FROZEN_STATUS!r} "
                          "with frozen_before_outcomes true")
    return proto


def verify_pins(proto: dict) -> None:
    """Refuse when a private input differs from the sha256 the frozen protocol pinned for it."""
    for name, sha in (proto.get("pinned_artifacts") or {}).items():
        path = PRIVATE / name
        if not path.exists() or sha256_file(path) != sha:
            raise FreezeError(f"refused: private artifact {name} does not match its pinned sha256")


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
