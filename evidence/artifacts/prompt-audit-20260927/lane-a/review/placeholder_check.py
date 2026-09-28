"""For every published lane-A copy whose hash differs from its frozen or sent hash, check that it is the original after
the packager's replacements and nothing else.

usage: placeholder_check.py LANE_A_DIR [OUT]
Runs from the coordinator's private work directory. Each original is found there by its frozen or sent sha256 among the
files with the same name. The packager's own clean() (package_lane_a.py, read up to its first packaging step) is
applied to it, and the result is compared with the published copy. The packager numbers subagent ids across the whole
package, so <agent-id-N> is compared as <agent-id>. Prints list labels, file names and verdicts only.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

L = Path(sys.argv[1]).resolve()
AD = Path(__file__).resolve().parent.parent
A2 = AD.parent
W3 = A2.parent
HOLD = W3.parent
S = HOLD.parent
BASES = (A2, S / "j7" / "x5c", HOLD / "k2", HOLD / "j6" / "x5", W3 / "lane-a")

packager = A2 / "package_lane_a.py"
head = packager.read_text().split("\n# Round 1:", 1)[0]
argv, sys.argv = sys.argv, [str(packager), str(HOLD / "wt-x5")]
ns = {"__file__": str(packager), "__name__": "package_lane_a_head"}
exec(compile(head, str(packager), "exec"), ns)
sys.argv = argv
clean = ns["clean"]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def norm(text):
    return re.sub(r"<agent-id-\d+>", "<agent-id>", text)


def published(base, name, digest):
    direct = base / name
    if direct.is_file():
        return direct
    hits = [p for p in base.rglob(Path(name).name) if p.is_file()]
    if len(hits) == 1:
        return hits[0]
    same = [q for q in L.rglob(Path(name).name) if q.is_file()]
    return next((q for q in same if sha(q) == digest), same[0] if len(same) == 1 else None)


lists = [(str(p.relative_to(L)), p.parent, [ln.split(None, 1)[::-1] for ln in p.read_text().splitlines() if ln.strip()])
         for p in sorted(L.rglob("frozen-*.sha256"))]
lists += [(str(p.relative_to(L)), p.parent, list(json.loads(p.read_text())["files"].items()))
          for p in sorted(L.rglob("sent-sha256.json"))]
report, bad = {}, 0
for label, base, entries in lists:
    rows = {}
    for name, digest in entries:
        digest = digest.strip()
        name = name.replace("j7/x5c/", "")
        name = name[len("k2/"):] if name.startswith("k2/") else name
        pub = published(base, name, digest)
        if pub is None or sha(pub) == digest:
            continue
        orig = next((p for b in BASES for p in b.rglob(Path(name).name) if p.is_file() and sha(p) == digest), None)
        if orig is None:
            rows[name] = "original not found"
        else:
            text = clean(orig.read_text(encoding="utf-8"))
            text = text if text.endswith("\n") else text + "\n"
            same = norm(text) == norm(pub.read_text(encoding="utf-8"))
            rows[name] = "differs only by the packager's replacements" if same else "differs beyond the replacements"
        bad += rows[name] != "differs only by the packager's replacements"
    report[label] = rows
    print(label)
    for n, v in rows.items():
        print("   ", v, n)
if len(sys.argv) > 2:
    Path(sys.argv[2]).write_text(json.dumps({"note": "Each published copy whose hash differs from its frozen or sent "
                                             "hash, compared with the packager's clean() applied to the original "
                                             "found by that hash; <agent-id-N> is compared as <agent-id>.",
                                             "lists": report}, indent=1) + "\n")
sys.exit(1 if bad else 0)
