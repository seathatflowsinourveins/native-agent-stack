#!/usr/bin/env python3
"""Synthetic fixture for tree_drift_check.py's upstream-gitlink control: `gh` with one gitlink added.

Runs the real `gh` with the same arguments and passes its output through, except for a
`git/trees/` listing. There it adds one gitlink row (mode 160000, type commit, pointing at the
pinned commit) directly under PATH, and rewrites PATH's own row to the tree that git would write
with that entry. The listing stays self-consistent, and the manifest's tree_sha becomes the stale
one. Before rewriting, the fixture checks that its own hashing reproduces the listed PATH row.
The tree is hashed as git v2.43.0 builtin/mktree.c write_tree hashes one (tree.c
base_name_compare order). The fixture writes nothing.

Usage, from the root of a checkout of this repository:
  python3 evidence/artifacts/skills-listing-restore-20260928/tree_drift_check.py --checkout . \
      --skill supply-chain-risk-auditor --allow scripts/uv.lock \
      --gh evidence/artifacts/skills-listing-restore-20260928/fixture_gh_gitlink.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys

PATH = "plugins/supply-chain-risk-auditor/skills/supply-chain-risk-auditor"
GITLINK = {"path": PATH + "/vendored", "mode": "160000", "type": "commit",
           "sha": "0cc1c73a5e96749ab32d7ea5e14892fafa6972ae"}


def tree_sha(rows: list[dict]) -> str:
    entries = [(row["path"].rsplit("/", 1)[1].encode(), row["mode"].lstrip("0").encode(), bytes.fromhex(row["sha"]),
                row["type"] == "tree") for row in rows]
    entries.sort(key=lambda entry: entry[0] + b"/" if entry[3] else entry[0])
    body = b"".join(mode + b" " + name + b"\0" + digest for name, mode, digest, _ in entries)
    return hashlib.sha1(b"tree %d\0" % len(body) + body).hexdigest()


def main() -> int:
    done = subprocess.run(["gh", *sys.argv[1:]], capture_output=True, stdin=subprocess.DEVNULL, check=False)
    if done.returncode != 0 or len(sys.argv) < 3 or "/git/trees/" not in sys.argv[2]:
        sys.stdout.buffer.write(done.stdout)
        sys.stderr.buffer.write(done.stderr)
        return done.returncode
    listing = json.loads(done.stdout)
    folder = next(row for row in listing["tree"] if row["path"] == PATH)
    children = [row for row in listing["tree"]
                if row["path"].startswith(PATH + "/") and "/" not in row["path"][len(PATH) + 1:]]
    if tree_sha(children) != folder["sha"]:
        print("fixture: its hashing does not reproduce the listed folder row", file=sys.stderr)
        return 3
    folder["sha"] = tree_sha(children + [GITLINK])
    listing["tree"].append(dict(GITLINK))
    sys.stdout.write(json.dumps(listing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
