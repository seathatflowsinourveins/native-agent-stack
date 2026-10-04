#!/usr/bin/env python3
"""Structural, value-free comparison of two JSON config files (hash + key paths only).

Usage: settings_diff.py OLD NEW
Prints sha256 prefixes, ai-memory hook command counts, and the key paths that differ.
Values are never printed; paths under /env are collapsed to a count.
"""
import hashlib
import json
import sys


def paths(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for key, val in obj.items():
            out.update(paths(val, f"{prefix}/{key}"))
    elif isinstance(obj, list):
        out[prefix] = ("list", len(obj), hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest())
    else:
        out[prefix] = ("scalar", hashlib.sha256(json.dumps(obj).encode()).hexdigest())
    return out


def redact(path):
    return "/env/<name>" if path.startswith("/env/") else path


def main():
    old_raw = open(sys.argv[1], "rb").read()
    new_raw = open(sys.argv[2], "rb").read()
    res = {"old_sha256": hashlib.sha256(old_raw).hexdigest(), "new_sha256": hashlib.sha256(new_raw).hexdigest()}
    for label, raw in (("old", old_raw), ("new", new_raw)):
        res[f"{label}_cmds"] = {v: raw.count(f"tools/ai-memory-{v}/ai-memory".encode())
                                for v in ("2.3.2", "2.4.0", "2.4.1")}
    old, new = json.loads(old_raw), json.loads(new_raw)
    po, pn = paths(old), paths(new)
    res["only_in_new"] = sorted({redact(p) for p in pn if p not in po})
    res["only_in_old"] = sorted({redact(p) for p in po if p not in pn})
    changed = []
    for p in sorted(p for p in po if p in pn and po[p] != pn[p]):
        o, n = po[p], pn[p]
        changed.append({"path": redact(p), "old": o[:2] if o[0] == "list" else "scalar",
                        "new": n[:2] if n[0] == "list" else "scalar"})
    res["changed_paths"] = changed
    res["hooks_subtree_identical"] = old.get("hooks") == new.get("hooks")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
