"""Set line 3 of the portable Claude template in the X5 worktree (wt-x5) to one of two texts, by exact match of the
line's whole current content, to measure X5a before it is proposed again.

usage: apply_x5a_trial.py control|proposal
- control: the round-1 proposed text (proposals.json X5a "new"), which opens its second sentence with a capital
  "Never" and is expected to fail PortableTopRuleTests' case-sensitive phrase check;
- proposal: the round-1 amendment that keeps the installed client as a source of truth (lane-a/gpt6.json X5a
  resolution_text), proposed for round 2.
Line 3 may currently hold the base text or either of these two.
"""
import json
import sys
from pathlib import Path

W3 = Path(__file__).resolve().parent.parent
WT = W3.parent / "wt-x5"
item = next(i for i in json.loads((W3 / "proposals.json").read_text())["items"] if i["id"] == "X5a")
amend = next(i for i in json.loads((W3 / "lane-a" / "gpt6.json").read_text())["items"] if i["id"] == "X5a")
texts = {"base": item["old"], "control": item["new"], "proposal": amend["resolution_text"]}
want = texts[sys.argv[1]]
path = WT / item["file"]
lines = path.read_text(encoding="utf-8").split("\n")
current = [k for k, t in texts.items() if lines[2] == t]
assert current, "line 3 holds none of the known texts"
lines[2] = want
path.write_text("\n".join(lines), encoding="utf-8")
print(json.dumps({"file": item["file"], "was": current[0], "now": sys.argv[1], "line3_words": len(want.split()),
                  "file_words": len(path.read_text(encoding="utf-8").split())}))
