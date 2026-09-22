"""Diff two fixture manifests (see fixture.py) and print a structured summary
of path/kind/mode/size/hash/symlink-target/xattr/ACL/hardlink differences."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def load(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text())
    return {e["path"]: e for e in data}


def diff(before_path: Path, after_path: Path) -> dict:
    before = load(before_path)
    after = load(after_path)
    missing = sorted(set(before) - set(after))
    added = sorted(set(after) - set(before))
    changed = {}
    for path in sorted(set(before) & set(after)):
        b, a = before[path], after[path]
        deltas = {}
        for key in sorted(set(b) | set(a)):
            if key == "inode_group":
                continue  # local numbering may legitimately differ
            if b.get(key) != a.get(key):
                deltas[key] = {"before": b.get(key), "after": a.get(key)}
        if deltas:
            changed[path] = deltas
    # hardlink group preservation: compare *sets* of paths sharing an inode
    def groups(m: dict[str, dict]) -> dict[int, list[str]]:
        g: dict[int, list[str]] = {}
        for path, e in m.items():
            if e.get("kind") == "file" and "inode_group" in e:
                g.setdefault(e["inode_group"], []).append(path)
        return {k: sorted(v) for k, v in g.items() if len(v) > 1}

    before_groups = sorted(groups(before).values())
    after_groups = sorted(groups(after).values())
    return {
        "missing_paths": missing,
        "added_paths": added,
        "changed_paths": changed,
        "hardlink_groups_before": before_groups,
        "hardlink_groups_after": after_groups,
        "hardlink_groups_preserved": before_groups == after_groups,
    }


if __name__ == "__main__":
    result = diff(Path(sys.argv[1]), Path(sys.argv[2]))
    print(json.dumps(result, indent=2, sort_keys=True))
