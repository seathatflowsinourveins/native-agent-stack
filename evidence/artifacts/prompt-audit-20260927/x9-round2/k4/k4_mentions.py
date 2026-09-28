"""Retain, per K4 run, the sentences of the full answer that cite the plugin's commands from the session's skill list.

usage: k4_mentions.py RESULTS_K4_JSON OUT_JSON
The packet's count ("N of 9 answers cite claude-hud:setup or claude-hud:configure") was computed from the full
answers, which are not published (the K4 answers also quote client settings). This keeps only each matching sentence,
cut to 300 characters, so the count can be recomputed from retained text. Host paths are replaced by "~".
"""
import json
import re
import sys
from pathlib import Path

MENTION = re.compile(r"claude-hud:(?:setup|configure)")
rows = json.loads(Path(sys.argv[1]).read_text())["results"]["results"]
out = {"note": __doc__.split("\n\n", 1)[1].strip(), "pattern": MENTION.pattern, "runs": []}
for r in rows:
    s = json.loads(r["response"]["output"])
    final = re.sub(r"/home/[A-Za-z0-9_.-]+", "~", s.get("final") or "")
    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+", final) if MENTION.search(x)]
    out["runs"].append({"arm": r["provider"]["label"].removeprefix("arm-"), "transcript": s["transcript"],
                        "model": (s.get("init") or {}).get("model"), "cites": bool(sentences),
                        "sentences": [x[:300] for x in sentences]})
counts = {a: sum(x["cites"] for x in out["runs"] if x["arm"] == a) for a in ("g", "c", "0")}
out["counts"] = {**counts, "total": sum(counts.values()), "runs": len(out["runs"])}
Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
print(json.dumps(out["counts"]))
for x in out["runs"]:
    print(x["arm"], x["model"], x["cites"], [y[:160] for y in x["sentences"]])
