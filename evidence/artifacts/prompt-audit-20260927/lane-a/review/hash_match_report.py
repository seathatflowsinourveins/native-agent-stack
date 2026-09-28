"""Which published lane-A files still match the hashes of the files as frozen or sent.

usage: hash_match_report.py LANE_A_DIR [OUT]
For each frozen-*.sha256 list (frozen-a2.sha256, frozen-final.sha256) and each sent-sha256.json, find the published copy of every listed file (by its path under the
list's directory, else by a unique basename under it) and print match, differs or not published. Prints file names and
verdicts only.
"""
import hashlib
import json
import sys
from pathlib import Path

L = Path(sys.argv[1])


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def find(base, name):
    direct = base / name
    if direct.is_file():
        return direct
    hits = [p for p in base.rglob(Path(name).name) if p.is_file()]
    return hits[0] if len(hits) == 1 else None


lists = [(str(p.relative_to(L)), p.parent, [ln.split(None, 1)[::-1] for ln in p.read_text().splitlines() if ln.strip()])
         for p in sorted(L.rglob("frozen-*.sha256"))]
for p in sorted(L.rglob("sent-sha256.json")):
    files = json.loads(p.read_text())["files"]
    lists.append((str(p.relative_to(L)), p.parent, [(k, v) for k, v in files.items()]))
report = {}
for label, base, entries in lists:
    rows = {}
    for name, digest in entries:
        name = name.replace("j7/x5c/", "")
        name = name[len("k2/"):] if name.startswith("k2/") else name  # the lane files, published beside the list
        pub = find(base, name)
        if pub is None:  # published elsewhere in the package: any same-named copy that matches counts
            same = [q for q in L.rglob(Path(name).name) if q.is_file()]
            pub = next((q for q in same if sha(q) == digest.strip()), same[0] if len(same) == 1 else None)
        rows[name] = "not published" if pub is None else ("match" if sha(pub) == digest.strip() else "differs")
    report[label] = rows
    print(label, {k: sum(1 for v in rows.values() if v == k) for k in ("match", "differs", "not published")})
    for n, v in rows.items():
        if v != "match":
            print("   ", v, n)
Path(sys.argv[2]).write_text(json.dumps(report, indent=1) + "\n") if len(sys.argv) > 2 else None
