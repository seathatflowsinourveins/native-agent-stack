"""Scan the attempt-2 repository root for void_patterns.MAPPING and PHRASES (strings that map an X9 text to a lane).

usage: root_scan.py ROOT
Prints the file count and the files with a match (none expected); reads text with undecodable bytes ignored.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "x9-round2"))
import void_patterns as v  # noqa: E402

root = Path(sys.argv[1])
hits, n = {"MAPPING": [], "PHRASES": []}, 0
for d, _, files in os.walk(root):
    for f in files:
        p = Path(d) / f
        try:
            text = p.read_text(errors="ignore")
        except OSError:
            continue
        n += 1
        for k in hits:
            if getattr(v, k).search(text):
                hits[k].append(str(p.relative_to(root)))
print(f"{n} files scanned; files with a MAPPING match: {len(hits['MAPPING'])}; with a PHRASES match: "
      f"{len(hits['PHRASES'])}")
for k, files in hits.items():
    for f in files:
        print(k, f)
