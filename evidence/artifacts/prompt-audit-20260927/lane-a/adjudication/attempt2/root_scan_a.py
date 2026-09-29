"""Before dispatch: count repository-root files whose text matches lane A's MAPPING or PHRASES patterns (a judge
reading one would be voided although nothing leaked), root paths that match ACCESS, and the patterns' hits in each
file sent to the judges. Round 2's root_scan.py, with lane A's patterns and sent files.

usage: root_scan_a.py ADJ_DIR
"""
import json
import sys
from pathlib import Path

X = Path(__file__).resolve().parent
sys.path.insert(0, str(X))
import void_patterns_a as v  # noqa: E402

ADJ = Path(sys.argv[1])
ROOT = ADJ / "root"
counts, examples = {"MAPPING": 0, "PHRASES": 0}, {"MAPPING": [], "PHRASES": []}
access_paths, n = [], 0
for p in sorted(ROOT.rglob("*")):
    if not p.is_file():
        continue
    n += 1
    rel = str(p.relative_to(ROOT))
    if v.ACCESS.search("/" + rel):
        access_paths.append(rel)
    text = p.read_text(errors="replace")
    for name in counts:
        m = getattr(v, name).search(text)
        if m:
            counts[name] += 1
            if len(examples[name]) < 5:
                examples[name].append({"file": rel, "match": m.group(0)})
print(n, "root files;", counts, json.dumps(examples), "| root paths matching ACCESS:", access_paths[:10])
for d in ("adjudication-inputs", "prompts", "schemas"):
    for f in sorted((ADJ / d).iterdir()):
        t = f.read_text()
        print(f"{d}/{f.name}:", {k: bool(getattr(v, k).search(t)) for k in ("MAPPING", "PHRASES", "WEB")})
t = (ADJ / "packet.md").read_text()
print("packet.md:", {k: bool(getattr(v, k).search(t)) for k in ("MAPPING", "PHRASES", "WEB")})
