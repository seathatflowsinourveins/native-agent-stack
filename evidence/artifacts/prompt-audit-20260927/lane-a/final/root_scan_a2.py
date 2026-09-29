"""Before dispatch: count lane-root files whose text matches MAPPING or PHRASES (a judge reading one would be voided
although nothing leaked), root paths that match any ACCESS part of either lane, and each sent file's hits on every
pattern, including the client-configuration text of exposure_scan_dir.py. Lane A's root_scan_a.py for the final round.

usage: root_scan_a2.py K2_DIR
Exits 1 on any hit except WEB in a sent file: WEB voids only a web search or opened URL, and the sent files
name this repository in its own markers and in the session's scratchpad path, so it is reported, not failing.
"""
import re
import sys
from pathlib import Path

X = Path(__file__).resolve().parent
sys.path.insert(0, str(X))
import void_patterns_a2 as v  # noqa: E402

CONFIG = re.compile(r"enabledPlugins|statusLine|installed_plugins|known_marketplaces|plugins/cache"
                    r"|[a-z0-9-]+@[a-z0-9-]+\"?\s*:\s*true")
K2 = Path(sys.argv[1])
ROOT = K2 / "root"
acc = {**v.access("claude"), **{f"gpt6:{k}": r for k, r in v.access("gpt6").items()}}
counts, examples, access_paths, n = {"MAPPING": 0, "PHRASES": 0}, [], [], 0
for p in sorted(ROOT.rglob("*")):
    if not p.is_file():
        continue
    n += 1
    path = str(p)
    access_paths += [f"{k}: {p.relative_to(ROOT)}" for k, r in acc.items() if r.search(path)][:1]
    text = p.read_text(errors="replace")
    for name in counts:
        m = getattr(v, name).search(text)
        if m:
            counts[name] += 1
            examples.append({"file": str(p.relative_to(ROOT)), "pattern": name, "match": m.group(0)})
print(n, "root files;", counts, examples[:6], "| root paths matching ACCESS:", len(access_paths), access_paths[:6])
sent_hits = 0
for f in sorted([*(K2 / "packets").iterdir(), *(K2 / "prompts").iterdir(), *(K2 / "schemas").iterdir()]):
    t = f.read_text()
    hits = {k: bool(getattr(v, k).search(t)) for k in ("MAPPING", "PHRASES", "WEB")}
    hits.update({f"ACCESS:{k}": bool(r.search(t)) for k, r in acc.items()})
    hits["CONFIG"] = bool(CONFIG.search(t))
    on = [k for k, b in hits.items() if b]
    sent_hits += len([k for k in on if k != "WEB"])
    print(f"{f.parent.name}/{f.name}:", on or "clean")
sys.exit(1 if counts["MAPPING"] or counts["PHRASES"] or access_paths or sent_hits else 0)
