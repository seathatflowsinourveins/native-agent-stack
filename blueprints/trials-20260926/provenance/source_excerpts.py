#!/usr/bin/env python3
"""Extract pinned upstream source lines that a trial finding cites.

Usage: source_excerpts.py <items.json> > <source-review.json>

items.json is a list of {"id", "claim", "repository" (clone URL), "commit", "path", "lines": [start, end]}.
Each (repository, commit) pair is fetched once, by commit id, into a fresh temporary directory that is
removed afterwards. The output lists, per item, the file's git blob id and sha256 at that commit and the
exact cited lines, so a reader can re-check every excerpt against the named commit. This is source
review (inspection of pinned upstream files), not execution evidence; the claim text is the author's.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def main() -> int:
    items = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    checkouts: dict[tuple[str, str], Path] = {}
    results = []
    with tempfile.TemporaryDirectory() as work:
        for item in items:
            key = (item["repository"], item["commit"])
            if key not in checkouts:
                target = Path(work) / f"repo{len(checkouts)}"
                target.mkdir()
                git("init", "-q", cwd=target)
                git("remote", "add", "origin", item["repository"], cwd=target)
                git("fetch", "-q", "--depth", "1", "origin", item["commit"], cwd=target)
                git("checkout", "-q", "FETCH_HEAD", cwd=target)
                if git("rev-parse", "HEAD", cwd=target).strip() != item["commit"]:
                    raise SystemExit(f"{item['id']}: fetched commit differs from {item['commit']}")
                checkouts[key] = target
            checkout = checkouts[key]
            raw = (checkout / item["path"]).read_bytes()
            lines = raw.decode("utf-8").splitlines()
            start, end = item["lines"]
            if not 1 <= start <= end <= len(lines):
                raise SystemExit(f"{item['id']}: lines {start}-{end} outside 1-{len(lines)}")
            results.append({
                "id": item["id"],
                "claim": item["claim"],
                "repository": item["repository"],
                "commit": item["commit"],
                "path": item["path"],
                "lines": [start, end],
                "blob": git("rev-parse", f"HEAD:{item['path']}", cwd=checkout).strip(),
                "file_sha256": hashlib.sha256(raw).hexdigest(),
                "excerpt": "\n".join(lines[start - 1:end]),
            })
    json.dump({"schema_version": 1, "evidence_class": "source_review", "items": results}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
