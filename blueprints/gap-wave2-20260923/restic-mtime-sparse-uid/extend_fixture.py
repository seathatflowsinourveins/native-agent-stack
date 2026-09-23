"""Extend the gap-resolution-20260922 restic filesystem-semantics fixture
(blueprints/gap-resolution-20260922/restic-filesystem-semantics/fixture.py)
with the three items open_gaps[recovery-portability][6] still lists as
unmeasured after that check: timestamps (mtime/atime), UID/GID variation
(chown to a different owner) and sparse-block preservation on restore.

Reuses fixture.build()/fixture.manifest() unmodified so the original 10-entry
tree and its metadata fields stay comparable; this module only adds a
timestamp-aware manifest and a chown/sparse-block helper. Deterministic
synthetic content only; no client or personal data.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[2]
        / "gap-resolution-20260922" / "restic-filesystem-semantics"),
)
import fixture  # noqa: E402  (path-extended import of the original fixture)


def manifest_with_timestamps(root: Path, *, capture_ownership: bool = True) -> list[dict]:
    """Same as fixture.manifest() but additionally records st_mtime and
    st_atime (as integer seconds -- sub-second precision is not part of the
    preregistered claim, since restic's own docs note only second-granularity
    is guaranteed round-tripped by default).

    CORRECTED ORDERING (fix round, 2026-09-23): the timestamp lstat() pass
    MUST run before fixture.manifest(), not after. fixture.manifest() calls
    p.read_bytes() on every file to compute its sha256, and on a relatime-
    mounted filesystem, reading a file whose current atime predates its
    ctime (true immediately after any restore, and true here immediately
    after os.utime() stamps a fixed reference atime) moves atime to the
    time of that read. The original version of this function called
    fixture.manifest() FIRST and only then did its own lstat() pass, so the
    "atime" it recorded was already the self-inflicted post-read value, not
    the genuine pre-read/pre-restore atime. lstat() itself never touches
    atime (only open/read does), so capturing timestamps first and only
    then calling fixture.manifest() (whose reads are irrelevant once the
    real values are already captured) gives a correct reading on both
    sides of a restic round trip."""
    by_path = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        st = p.lstat()
        by_path[rel] = {
            "mtime": int(st.st_mtime),
            "atime": int(st.st_atime),
        }
    entries = fixture.manifest(root, capture_ownership=capture_ownership)
    for e in entries:
        ts = by_path.get(e["path"])
        if ts:
            e["mtime"] = ts["mtime"]
            e["atime"] = ts["atime"]
    return entries


def set_reference_timestamps(root: Path, *, mtime: int, atime: int) -> None:
    """Set a deterministic, non-'now' mtime/atime on every entry so the
    round-trip check cannot pass merely because both sides read 'now'."""
    for p in sorted(root.rglob("*"), reverse=True):
        os.utime(p, (atime, mtime), follow_symlinks=False)


def chown_probe_file(root: Path, *, uid: int, gid: int) -> dict:
    """Attempt `sudo -n chown` of one fixture file to a different UID/GID.
    Returns a dict recording whether this was runnable at all (per the task's
    'chown to another UID only if `sudo -n true` succeeds, otherwise record it
    as not runnable' instruction) and the chown outcome."""
    probe = subprocess.run(["sudo", "-n", "true"], capture_output=True, text=True)
    if probe.returncode != 0:
        return {
            "runnable": False,
            "reason": "sudo -n true failed (no passwordless sudo available)",
            "sudo_stderr": probe.stderr.strip(),
        }
    target = root / "plain.txt"
    before_uid = target.stat().st_uid
    result = subprocess.run(
        ["sudo", "-n", "chown", f"{uid}:{gid}", str(target)],
        capture_output=True, text=True,
    )
    after_uid = target.stat().st_uid if result.returncode == 0 else None
    return {
        "runnable": True,
        "chown_exit": result.returncode,
        "chown_stderr": result.stderr.strip(),
        "target": "plain.txt",
        "before_uid": before_uid,
        "requested_uid": uid,
        "requested_gid": gid,
        "after_uid": after_uid,
    }


def du_blocks(path: Path) -> dict:
    """Report allocated disk blocks (du, 512-byte block units by default with
    --block-size=512) vs apparent/logical size for a single file, to compare
    sparse-block preservation across restore modes."""
    real = subprocess.run(
        ["du", "--block-size=512", str(path)], capture_output=True, text=True, check=True
    ).stdout.split()[0]
    apparent = subprocess.run(
        ["du", "--apparent-size", "--block-size=512", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.split()[0]
    return {"allocated_512b_blocks": int(real), "apparent_512b_blocks": int(apparent)}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=["build-and-stamp", "manifest-ts", "chown-probe", "du-blocks"],
    )
    parser.add_argument("root", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--no-ownership", action="store_true")
    parser.add_argument("--uid", type=int, default=65534)
    parser.add_argument("--gid", type=int, default=65534)
    parser.add_argument("--ref-mtime", type=int, default=1_700_000_000)
    parser.add_argument("--ref-atime", type=int, default=1_700_000_500)
    parser.add_argument("--file", type=Path)
    args = parser.parse_args()

    if args.action == "build-and-stamp":
        fixture.build(args.root)
        set_reference_timestamps(args.root, mtime=args.ref_mtime, atime=args.ref_atime)
    elif args.action == "manifest-ts":
        m = manifest_with_timestamps(args.root, capture_ownership=not args.no_ownership)
        text = json.dumps(m, indent=2, sort_keys=True)
        (args.out.write_text(text) if args.out else print(text))
    elif args.action == "chown-probe":
        result = chown_probe_file(args.root, uid=args.uid, gid=args.gid)
        text = json.dumps(result, indent=2, sort_keys=True)
        (args.out.write_text(text) if args.out else print(text))
    elif args.action == "du-blocks":
        result = du_blocks(args.file)
        text = json.dumps(result, indent=2, sort_keys=True)
        (args.out.write_text(text) if args.out else print(text))
