"""docs/lanes.md's registration step for named files: host_receipts.register_file for each, run from the worktree root.

usage: register_files.py WORKTREE PATH...
"""
import sys
from pathlib import Path

wt = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(wt / "scripts"))
import host_receipts  # noqa: E402

for p in sys.argv[2:]:
    host_receipts.register_file(wt, p)
    print("registered", p)
