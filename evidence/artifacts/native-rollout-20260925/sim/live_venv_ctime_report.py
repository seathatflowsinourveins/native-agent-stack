#!/usr/bin/env python3
"""Report ctime-changed files under a root since a UTC cutoff (mtime-blind-spot aware).

Checked in during the round-3 fix for the major finding that the "live venv
unchanged" acceptance check used `find <root> -newermt <cutoff>`, which is
mtime-only: hardlink creation/removal on a shared-cache inode changes that
inode's ctime (a new/removed directory entry is metadata) but never touches
its mtime, so `-newermt` silently misses exactly the entanglement-fix
metadata churn this receipt needs to disclose. This host's `find`/`bfs`
rejected several `-newerct` timestamp forms tried during this round's
verification (`Invalid timestamp`), so this script does the equivalent
comparison directly via `os.lstat().st_ctime`, which is unambiguous.

This does not by itself prove file *content* is unchanged (ctime also
changes on a metadata-only chmod/chown or a hardlink to/from the file, with
no byte of the file itself touched) -- pair it with
verify_live_venv_content.py's RECORD-hash check for that.
"""
import datetime
import os
import sys


def main(argv):
    if len(argv) < 3:
        print("usage: live_venv_ctime_report.py <root> <cutoff_utc_iso> "
              "[--exclude-substring SUBSTR]", file=sys.stderr)
        print("  cutoff_utc_iso example: 2026-09-25T08:00:00+00:00", file=sys.stderr)
        return 2
    root = argv[1]
    cutoff = datetime.datetime.fromisoformat(argv[2])
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=datetime.timezone.utc)
    cutoff_ts = cutoff.timestamp()
    excludes = [argv[i + 1] for i, a in enumerate(argv) if a == "--exclude-substring"]

    total = 0
    changed = []
    for dirpath, dirnames, filenames in os.walk(root):
        if any(ex in dirpath for ex in excludes):
            continue
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            try:
                st = os.lstat(p)
            except FileNotFoundError:
                continue
            total += 1
            if st.st_ctime >= cutoff_ts:
                changed.append((st.st_ctime, st.st_mtime, st.st_nlink, p))

    print(f"root={root} cutoff={cutoff.isoformat()} total_files={total} "
          f"ctime_changed_since_cutoff={len(changed)}")
    mtime_also_changed = sum(1 for ct, mt, nl, p in changed if mt >= cutoff_ts)
    print(f"  of those, mtime_also_changed={mtime_also_changed} "
          f"(ctime_only={len(changed) - mtime_also_changed})")
    for ct, mt, nl, p in sorted(changed)[:10]:
        print(f"  ctime={datetime.datetime.fromtimestamp(ct, datetime.timezone.utc).isoformat()} "
              f"mtime={datetime.datetime.fromtimestamp(mt, datetime.timezone.utc).isoformat()} "
              f"nlink={nl} {p}")
    if len(changed) > 10:
        print(f"  ... and {len(changed) - 10} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
