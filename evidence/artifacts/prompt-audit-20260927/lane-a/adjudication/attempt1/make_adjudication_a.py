"""Build lane A's one adjudication round for the two items its lanes split on (X5a, X5c): round 1's
make_adjudication.py (convergence-prompt-audit/), with lane A's packet, items and returns.

Writes a staging copy of the adjudication directory, which is moved to its final place only after round 3's X9
judges finish (so the scratchpad lists nothing new while they run):
  <hold>/j5-stage/x5/  ->  <scratchpad>/j5/x5/   (the final path is the one every brief and input names)
    packet.md                         copy of the frozen lane-A packet
    adjudication-inputs/adjudicate.AB.md and adjudicate.BA.md   the same items, returns in both orders
    schemas/adjudicate.json           Codex-strict output schema
    prompts/adjudicate-{AB,BA}.txt    runner prompts (input inlined)
    prompts/claude-brief-{AB,BA}.txt  blind-adjudicator briefs (files by path)
The repository root (<final>/root, a plain export of 46184751) and the runner's work directory (<final>/runs) are
created at dispatch. Here, adjudication-mapping-a.json records which lane is A and B per item and order; it is never
shown to an adjudicator.

Anonymisation: one return's locators name the file its brief was delivered in (`…/claude-brief.txt:198`, and
"brief line 198" in its reasons); that line is the packet's line 192 (the operator's top rule), so both become
`packet.md:192`. Nothing else in either return is changed. The build fails if an identifying string remains.
"""
import hashlib
import json
import random
import re
import sys
from pathlib import Path

LANE = Path(__file__).resolve().parent
HOLD = LANE.parent.parent
S = HOLD.parent
FINAL = S / "j5" / "x5"
STAGE = HOLD / "j5-stage" / "x5"
ROOT = FINAL / "root"
MAX_PROMPT_BYTES = 120_000  # codex_job.py
BASE_COMMIT = "46184751"

packet = (LANE / "packet.md").read_text(encoding="utf-8")
PSHA = hashlib.sha256(packet.encode()).hexdigest()
if PSHA != (LANE / "packet.sha256").read_text().split()[0]:
    sys.exit("packet.md changed after freezing")
lanes = {k: {i["id"]: i for i in json.loads((LANE / f"{f}.json").read_text())["items"]}
         for k, f in (("g", "gpt6"), ("c", "claude"))}
lines = packet.splitlines()
if not lines[191].startswith("**Top rule: research convergence first; current upstream SOTA is the source of truth.**"):
    sys.exit("packet.md:192 is not the operator's top rule")

BRIEF_LOCATOR = re.compile(r"/tmp/\S*?/claude-brief\.txt:198")
IDENTIFYING = re.compile(r"/tmp/|scratchpad|claude-brief|gpt6|brief line|\bbrief\b|lane-a|convergence-r3|wt-r3-base"
                         r"|<session-id>|<user>|codex exec|\bopus\b|anthropic|openai", re.I)


def scrub(text):
    return BRIEF_LOCATOR.sub("packet.md:192", text).replace("brief line 198", "packet.md:192")


def section(item_id):
    m = re.search(rf"^## {item_id}: .*?(?=^---$|\Z)", packet, re.S | re.M)
    if not m:
        sys.exit(f"no packet section for {item_id}")
    return m.group(0).rstrip()


def packet_rules():
    start = packet.index("You are an independent reviewer.")
    end = packet.index("\n---\n", start)
    return packet[start:end].rstrip()


UNITS = ["X5a", "X5c"]


def effective(lane, item_id):
    r = lanes[lane][item_id]
    v = r["verdict"]
    if v == "reject":
        text = "Keep the current text; no edit."
    elif v == "agree":
        text = ("Agrees with the packet's proposed text for this item, exactly as written in the item above, applied "
                "together with the co-changes its reasons name as required in the same commit.")
    else:
        text = "Replacement (verbatim):\n\n```text\n" + r["resolution_text"] + "\n```"
    body = [f"Verdict: {v}", "", "Effective resolution: " + text, "", "Reasons: " + scrub(r["reasons"]), "",
            "Sources:"]
    body += [f"- `{scrub(s['locator'])}`: {json.dumps(scrub(s['quote']), ensure_ascii=False)}" for s in r["sources"]]
    out = "\n".join(body)
    m = IDENTIFYING.search(out)
    if m:
        sys.exit(f"{lane} {item_id}: identifying text remains: {out[max(0, m.start() - 60):m.end() + 60]!r}")
    return out


HEADER = """# Adjudication input: 2026-09-28 prompt-audit round 3, lane items X5a and X5c (order {order})

Two independent reviews judged the same frozen packet (`{final}/packet.md`, sha256 {psha}) and disagreed on the two
items below. For each item, choose the return whose effective resolution the evidence supports better, or `neither`.

Rules:
- The returns are anonymous (Return A and Return B). Do not try to identify who wrote them; judge the evidence only.
  Model and product names inside quoted sources or repository files are subject matter, not authorship.
- Verify, do not trust: excerpts here are copies. The original files are at the read-only repository root
  `{root}` (a plain export of {base}, the packet's base; the files these two items touch are identical at f508ffba,
  the main commit the items name).
- Choose `A`, `B` or `neither` per item. `neither` means the current text stays unchanged. Do not write new text:
  only a return's resolution can be applied, exactly as written, and nothing is merged across returns.
- A return's effective resolution includes any co-change its reasons name as required in the same commit; judge the
  resolution together with those co-changes.
- A resolution that another file, test or fixture would contradict or break, or that states something the repository
  or sources do not support, loses to one that does not. If both would, choose `neither`.
- Keep the operator's standing rules: licenses and incumbency are never selection criteria.
- Judge wording on whether the target models (Claude Code and Codex sessions that load these files) will follow it as
  intended, not on style.
- The packet's own rules and verdict meanings are quoted below; the returns' verdicts use them. Your answer is a
  choice among the returns, not a new verdict.
- Every `sources` entry names a file:line or URL and quotes the text that supports your choice.
- An item is applied only when every adjudication of it chooses the same resolution; otherwise it stays unchanged
  and both positions are recorded.

## The packet's rules (packet.md, verbatim)

{rules}
"""


def build(order, first_is_g):
    out = [HEADER.format(order=order, final=FINAL, psha=PSHA, root=ROOT, base=BASE_COMMIT, rules=packet_rules())]
    mapping = {}
    for unit, g_first in zip(UNITS, first_is_g):
        a, b = ("g", "c") if g_first else ("c", "g")
        mapping[unit] = {"A": a, "B": b}
        out.append("---\n\n# Item " + unit + "\n\n" + section(unit)
                   + "\n\n## Return A\n\n" + effective(a, unit) + "\n\n## Return B\n\n" + effective(b, unit) + "\n")
    return "\n".join(out), mapping


rng = random.Random(20260928)
first = [rng.random() < 0.5 for _ in UNITS]
for d in ("adjudication-inputs", "schemas", "prompts"):
    (STAGE / d).mkdir(parents=True, exist_ok=True)
(STAGE / "packet.md").write_text(packet, encoding="utf-8")

schema = {"type": "object", "additionalProperties": False, "required": ["items"], "properties": {"items": {
    "type": "array", "items": {"type": "object", "additionalProperties": False,
                               "required": ["id", "choice", "reasons", "sources", "confidence"], "properties": {
        "id": {"type": "string", "enum": UNITS},
        "choice": {"type": "string", "enum": ["A", "B", "neither"]},
        "reasons": {"type": "string"},
        "sources": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                               "required": ["locator", "quote"],
                                               "properties": {"locator": {"type": "string"},
                                                              "quote": {"type": "string"}}}},
        "confidence": {"type": "number"}}}}}}
(STAGE / "schemas" / "adjudicate.json").write_text(json.dumps(schema, indent=1) + "\n")

maps = {}
TASK = """Task: adjudicate the two items in the input below and answer only in the required JSON, one entry per item id
(X5a, X5c). Read the original files at the repository root named in the input; do not write, install or change
anything. You may search the web for current official documentation; cite official sources only.
"""
for order, flags in (("AB", first), ("BA", [not f for f in first])):
    text, maps[order] = build(order, flags)
    (STAGE / "adjudication-inputs" / f"adjudicate.{order}.md").write_text(text, encoding="utf-8")
    prompt = TASK + "\n" + text
    size = len(prompt.encode())
    if size > MAX_PROMPT_BYTES:
        sys.exit(f"runner prompt {order} is {size} bytes, over {MAX_PROMPT_BYTES}")
    (STAGE / "prompts" / f"adjudicate-{order}.txt").write_text(prompt, encoding="utf-8")
    brief = f"""Task: adjudicate the two items in {FINAL}/adjudication-inputs/adjudicate.{order}.md and answer only in JSON.
- Read that input file in full. It states the rules, and for each item the packet item, Return A and Return B.
- Verify claims against the original files under the repository root {ROOT} with Read, Grep and Glob, and against
  {FINAL}/packet.md. Read only these files and files under that root.
- Do not use memory, session-history or search-index tools (ai-memory, context-mode search, qmd, code indexes): the
  root above is the only source of repository truth, and the returns' authors must stay unknown to you.
- You have no web access. Do not write or change anything.
- Return only a JSON object that validates against {FINAL}/schemas/adjudicate.json: {{"items": [{{"id", "choice",
  "reasons", "sources": [{{"locator", "quote"}}], "confidence"}}]}}, exactly one entry per item id (X5a, X5c);
  choice is A, B or neither; confidence is 0..1. No prose outside the JSON.
"""
    (STAGE / "prompts" / f"claude-brief-{order}.txt").write_text(brief, encoding="utf-8")
    print(order, "runner prompt bytes", size, "input bytes", len(text.encode()))
(LANE / "adjudication-mapping-a.json").write_text(json.dumps(maps, indent=1) + "\n")
for p in sorted(STAGE.rglob("*")):
    if p.is_file():
        print(hashlib.sha256(p.read_bytes()).hexdigest()[:8], p.relative_to(STAGE))
print(json.dumps(maps))
