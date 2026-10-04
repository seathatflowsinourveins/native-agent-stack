"""Recompute lane A's published outcomes from the files in this directory and check them against the repository.

usage: python3 verify_lane_a.py        (from any directory; exits 1 on any mismatch)
- final/tally-final.json: the final round's two lanes, recomputed from final/gpt6.json and final/claude.json under
  the packet's rule (both agree: apply; both reject: keep; the same amendment: apply; otherwise adjudicate);
- final/adjudication/tally-adjudication-final.json: the X5c adjudication, recomputed from the four published
  judgments, the mapping and the audit (applied only when all four valid judgments choose one resolution);
- the repository: examples/claude-native/CLAUDE.md:3 holds X5a's applied text, the Codex template's line 3 holds
  X5c's applied text, and tests/test_codex_worker_lane.py's TOP_RULE_SHA256 and word count match the template's
  top-rule block as the test module's own template_segments() reads it.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

X = Path(__file__).resolve().parent
ROOT = X.parents[3]
bad = []


def load(path):
    return json.loads((X / path).read_text(encoding="utf-8"))


def lane_outcome(v):
    if v["gpt6"]["verdict"] == v["claude"]["verdict"] == "agree":
        return "apply the proposed change"
    if v["gpt6"]["verdict"] == v["claude"]["verdict"] == "reject":
        return "keep the current text"
    if (v["gpt6"]["verdict"] == v["claude"]["verdict"] == "amend"
            and v["gpt6"]["resolution_text"].strip() == v["claude"]["resolution_text"].strip()):
        return "apply the common amendment"
    return "adjudicate"


lanes = {k: {i["id"]: i for i in load(f"final/{k}.json")["return"]["items"]} for k in ("gpt6", "claude")}
tally = load("final/tally-final.json")
for unit in ("X5a", "X5c"):
    want = lane_outcome({k: lanes[k][unit] for k in lanes})
    got = tally["items"][unit]["outcome"]
    print(f"final round {unit}: {want}")
    if not got.startswith(want):
        bad.append(f"final round {unit}: published {got!r}, recomputed {want!r}")

mapping = load("final/adjudication/adjudication-mapping-final.json")["orders"]
audit = load("final/adjudication/audit-final.json")["judgments"]
chosen = {}
for fam in ("gpt6", "claude"):
    for order in ("AB", "BA"):
        ret = load(f"final/adjudication/{fam}.{order}.json")["return"]
        items = ret.get("items") or []
        valid = (not ret.get("leak") and len(items) == 1 and items[0].get("id") == "X5c"
                 and not audit[f"{fam}-{order}"]["void"])
        chosen[f"{fam}-{order}"] = mapping[order]["X5c"].get(items[0]["choice"], "neither") if valid else "invalid"
res = set(chosen.values())
want = ("apply the amendment (c)" if res == {"c"} else "apply the packet's proposal (g)" if res == {"g"}
        else "keep the current text")
got = load("final/adjudication/tally-adjudication-final.json")["outcome"]
print("X5c adjudication:", chosen, "->", want)
if not got.startswith(want.split(" (")[0]):
    bad.append(f"X5c adjudication: published {got!r}, recomputed {want!r}")

packet = (X / "final/packets/packet.md").read_text(encoding="utf-8")
x5a_text = re.search(r"^## X5a: .*?^Proposed text: (.*?)$", packet, re.S | re.M).group(1)
x5c_text = lanes["claude"]["X5c"]["resolution_text"].strip() if want.startswith("apply the amendment") else None
claude_md = (ROOT / "examples/claude-native/CLAUDE.md").read_text(encoding="utf-8").split("\n")[2]
template = (ROOT / "adoption/templates/codex.AGENTS.template.md").read_text(encoding="utf-8").split("\n")[2]
if claude_md != x5a_text:
    bad.append("examples/claude-native/CLAUDE.md:3 is not X5a's applied text")
if x5c_text is not None and template != x5c_text:
    bad.append("adoption/templates/codex.AGENTS.template.md:3 is not X5c's applied text")
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
from tests import test_codex_worker_lane as t  # noqa: E402

top, _, _ = t.template_segments()
test_text = (ROOT / "tests/test_codex_worker_lane.py").read_text(encoding="utf-8")
words = int(re.search(r"self\.assertEqual\(len\(top\.split\(\)\), (\d+)\)", test_text).group(1))
sha = hashlib.sha256(top.encode("utf-8")).hexdigest()
print("repository: CLAUDE.md:3 and template:3 checked; top-rule block", sha[:8], len(top.split()), "words")
if sha != t.TOP_RULE_SHA256 or len(top.split()) != words:
    bad.append(f"the pin does not match the template: {sha} {len(top.split())} vs {t.TOP_RULE_SHA256} {words}")
for b in bad:
    print("MISMATCH:", b)
print("all checks passed" if not bad else f"{len(bad)} mismatch(es)")
sys.exit(1 if bad else 0)
