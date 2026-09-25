#!/usr/bin/env python3
"""Verify a venv's installed file *content* against its own pip/uv RECORD hashes.

Checked in during the round-3 fix for two related findings:

1. (major) The "live venv unchanged" acceptance check used
   `find <root> -newermt <cutoff>`, which is mtime-only. This round's own
   copy-mode relink fix (rm -rf of the entangled new roots) decremented nlink
   and updated ctime -- not mtime -- on thousands of the live venv's files
   (removing a hardlink changes the shared inode's ctime but not its mtime).
   An mtime-only check cannot see that, so it under-reports what touched the
   forbidden root.
2. (minor) adaptive-paper.json's `a9970b71...` aggregate "checkpoint" hash of
   the live venv's site-packages had no committed script recording its exact
   encoding, so it was not independently reproducible (round 3 tried several
   plausible path/separator encodings and none reproduced it).

Rather than reverse-engineer the exact byte encoding a9970b71 used, this
script uses a different, *already content-addressed* baseline that needs no
new encoding decision and predates this track entirely: pip/uv write a
sha256 (urlsafe-base64, no padding) for every installed file into each
distribution's RECORD at install time. Re-hashing every file on disk today
and comparing it against its own RECORD entry proves file *content* is
unchanged since install (2026-09-19 for the live venv), independent of any
ctime/mtime/nlink metadata churn from hardlink creation or removal.

This is a regression check, not a repository test-suite member (this track's
brief allows writing only under evidence/artifacts/native-rollout-20260925/sim/
and docs/native-rollout-20260925-sim.md, not tests/): run it again after any
future round's work touching a root that shares uv's cache and it will raise
on the first content byte that actually changed.
"""
import base64
import glob
import hashlib
import os
import sys


def verify_root(root):
    record_files = sorted(glob.glob(
        os.path.join(root, "lib/python3.12/site-packages/*.dist-info/RECORD")))
    total = 0
    verified = 0
    mismatches = []
    missing = []
    for rf in record_files:
        base = os.path.dirname(os.path.dirname(rf))  # site-packages dir
        with open(rf, "r", errors="replace") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line:
                    continue
                parts = line.split(",")
                if len(parts) < 3:
                    continue
                relpath, hashfield = parts[0], parts[1]
                if not hashfield.startswith("sha256="):
                    continue
                total += 1
                fpath = os.path.join(base, relpath)
                if not os.path.exists(fpath):
                    missing.append(fpath)
                    continue
                with open(fpath, "rb") as f:
                    digest = hashlib.sha256(f.read()).digest()
                b64 = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
                expected = hashfield[len("sha256="):]
                if b64 == expected:
                    verified += 1
                else:
                    mismatches.append((fpath, expected, b64))
    return {
        "root": root,
        "record_files": len(record_files),
        "total_hashed_entries": total,
        "verified": verified,
        "mismatches": mismatches,
        "missing": missing,
    }


def main(argv):
    if len(argv) < 2:
        print("usage: verify_live_venv_content.py <venv_root> [venv_root ...]",
              file=sys.stderr)
        return 2
    overall_ok = True
    for root in argv[1:]:
        r = verify_root(root)
        ok = not r["mismatches"] and not r["missing"] and r["total_hashed_entries"] > 0
        overall_ok &= ok
        print(f"{r['root']}: dist-info RECORD files={r['record_files']} "
              f"hashed_entries={r['total_hashed_entries']} verified={r['verified']} "
              f"mismatches={len(r['mismatches'])} missing={len(r['missing'])} "
              f"{'OK' if ok else 'FAIL'}")
        for fpath, expected, got in r["mismatches"][:20]:
            print(f"  MISMATCH {fpath} expected={expected} got={got}")
        for fpath in r["missing"][:20]:
            print(f"  MISSING {fpath}")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
