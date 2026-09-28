"""Attempt 2 of lane A's X5a/X5c adjudication (attempt 1: adj/attempt1/void.json), in the blind-adjudicator
contract's format (.claude/agents/blind-adjudicator.md): a JSON input per order under adjudication-inputs/, one JSON
packet under packets/, and a task with the labelled lines Input file:, Packet file: and Repository root:. The items,
returns, mapping and rules are attempt 1's (make_adjudication_a.py, same seed); only their container changes, and the
input names no host path other than the repository root the task gives.

Writes a staging copy, moved to its final place after attempt 1's runner jobs finish:
  <hold>/j6-stage/x5/  ->  <scratchpad>/j6/x5/
    adjudication-inputs/x5.AB.json and x5.BA.json   question, rules, choices and, per item, the packet item and
                                                     Return A and Return B
    packets/x5.json                   the frozen lane-A packet (text and sha256)
    schemas/adjudicate.json           Codex-strict output schema (the runner's; the blind-adjudicator adds leak fields)
    prompts/judge-{AB,BA}.txt         runner prompts (input and packet inlined)
    prompts/claude-task-{AB,BA}.txt   blind-adjudicator tasks
The repository root (<final>/root, a plain export of 46184751) and the runner's work directory (<final>/runs) are
created at dispatch. The mapping stays in adjudication-mapping-a.json (never shown to an adjudicator).
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
FINAL = S / "j6" / "x5"
STAGE = HOLD / "j6-stage" / "x5"
ROOT = FINAL / "root"
MAX_PROMPT_BYTES = 120_000  # codex_job.py
BASE_COMMIT = "46184751"

packet = (LANE / "packet.md").read_text(encoding="utf-8")
PSHA = hashlib.sha256(packet.encode()).hexdigest()
if PSHA != (LANE / "packet.sha256").read_text().split()[0]:
    sys.exit("packet.md changed after freezing")
lanes = {k: {i["id"]: i for i in json.loads((LANE / f"{f}.json").read_text())["items"]}
         for k, f in (("g", "gpt6"), ("c", "claude"))}
if not packet.splitlines()[191].startswith("**Top rule: research convergence first; current upstream SOTA is the "
                                           "source of truth.**"):
    sys.exit("packet.md:192 is not the operator's top rule")

BRIEF_LOCATOR = re.compile(r"/tmp/\S*?/claude-brief\.txt:198")
IDENTIFYING = re.compile(r"/tmp/|/home/|scratchpad|claude-brief|gpt6|gpt-|brief line|\bbrief\b|lane-a|convergence-r3"
                         r"|wt-r3-base|<session-id>|<user>|codex exec|\bopus\b|sonnet|haiku|fable|mythos|astra|\bo3\b|\bo4\b"
                         r"|anthropic|openai|\"(?:lane|model|provenance|refutation)\":", re.I)


def scrub(text):
    return BRIEF_LOCATOR.sub("packet.md:192", text).replace("brief line 198", "packet.md:192")


def section(item_id):
    m = re.search(rf"^## {item_id}: .*?(?=^---$|\Z)", packet, re.S | re.M)
    if not m:
        sys.exit(f"no packet section for {item_id}")
    return m.group(0).rstrip()


def packet_rules():
    start = packet.index("You are an independent reviewer.")
    return packet[start:packet.index("\n---\n", start)].rstrip()


UNITS = ["X5a", "X5c"]


def effective(key, item_id):
    r = lanes[key][item_id]
    v = r["verdict"]
    if v == "reject":
        text = "Keep the current text; no edit."
    elif v == "agree":
        text = ("Agrees with the packet's proposed text for this item, exactly as written in the item, applied together "
                "with the co-changes its reasons name as required in the same commit.")
    else:
        text = "Replacement (verbatim): " + r["resolution_text"]
    return {"verdict": v, "effective_resolution": text, "reasons": scrub(r["reasons"]),
            "sources": [{"locator": scrub(s["locator"]), "quote": scrub(s["quote"])} for s in r["sources"]]}


RULES = [
    "The returns are anonymous (Return A and Return B). Do not try to identify who wrote them; judge the evidence only. "
    "Model and product names inside quoted sources or repository files are subject matter, not authorship.",
    "Verify, do not trust: excerpts here are copies. The original files are under the repository root the task names.",
    "Choose A, B or neither per item. neither means the current text stays unchanged. Do not write new text: only a "
    "return's resolution can be applied, exactly as written, and nothing is merged across returns.",
    "A return's effective resolution includes any co-change its reasons name as required in the same commit; judge the "
    "resolution together with those co-changes.",
    "A resolution that another file, test or fixture would contradict or break, or that states something the repository "
    "or sources do not support, loses to one that does not. If both would, choose neither.",
    "Keep the operator's standing rules: licenses and incumbency are never selection criteria.",
    "Judge wording on whether the target models (Claude Code and Codex sessions that load these files) will follow it "
    "as intended, not on style.",
    "The packet's own rules and verdict meanings are quoted in packet_rules_verbatim; the returns' verdicts use them. "
    "Your answer is a choice among the returns, not a new verdict.",
    "Every sources entry names a file:line or URL and quotes the text that supports your choice.",
    "An item is applied only when every adjudication of it chooses the same resolution; otherwise it stays unchanged "
    "and both positions are recorded."]


def build(order, first_is_g):
    doc = {"unit": "X5", "items_in_unit": UNITS,
           "question": ("Two independent reviews judged the same frozen packet (the packet file, sha256 " + PSHA + ") and "
                        "disagreed on the two items below. For each item, choose the return whose effective resolution "
                        "the evidence supports better, or neither."),
           "repository_root": (f"a plain export of commit {BASE_COMMIT}, the packet's base; the files these two items "
                               "touch are identical at f508ffba, the main commit the items name"),
           "choices": {"A": "apply Return A's effective resolution exactly as written",
                       "B": "apply Return B's effective resolution exactly as written",
                       "neither": "the current text stays unchanged"},
           "rules": RULES, "packet_rules_verbatim": packet_rules(), "items": []}
    mapping = {}
    for unit, g_first in zip(UNITS, first_is_g):
        a, b = ("g", "c") if g_first else ("c", "g")
        mapping[unit] = {"A": a, "B": b}
        doc["items"].append({"id": unit, "packet_item": section(unit), "return_A": effective(a, unit),
                             "return_B": effective(b, unit)})
    text = json.dumps(doc, ensure_ascii=False, indent=1) + "\n"
    returns = json.dumps([i[k] for i in doc["items"] for k in ("return_A", "return_B")], ensure_ascii=False)
    m = IDENTIFYING.search(returns)
    if m:
        sys.exit(f"{order}: identifying text remains: {returns[max(0, m.start() - 60):m.end() + 60]!r}")
    return text, mapping


rng = random.Random(20260928)
first = [rng.random() < 0.5 for _ in UNITS]
for d in ("adjudication-inputs", "packets", "schemas", "prompts"):
    (STAGE / d).mkdir(parents=True, exist_ok=True)
packet_json = json.dumps({"packet_sha256": PSHA, "base": BASE_COMMIT, "packet": packet}, ensure_ascii=False,
                         indent=1) + "\n"
(STAGE / "packets" / "x5.json").write_text(packet_json, encoding="utf-8")
schema = json.loads((LANE / "adj" / "schema-adjudicate.json").read_text())
(STAGE / "schemas" / "adjudicate.json").write_text(json.dumps(schema, indent=1) + "\n")

maps = {}
for order, flags in (("AB", first), ("BA", [not f for f in first])):
    text, maps[order] = build(order, flags)
    (STAGE / "adjudication-inputs" / f"x5.{order}.json").write_text(text, encoding="utf-8")
    prompt = (f"Task: adjudicate unit X5 (items X5a and X5c) and answer only in the required JSON, one entry per item "
              f"id. The input and the packet are below. The original files are under the read-only repository root "
              f"{ROOT} (a plain export of commit {BASE_COMMIT}); read them there. Do not write, install or change "
              f"anything. You may search the web for current official documentation; cite official sources only.\n\n"
              f"# Input file (x5.{order}.json)\n\n```json\n{text}```\n\n# Packet file (x5.json)\n\n```json\n"
              f"{packet_json}```\n")
    size = len(prompt.encode())
    if size > MAX_PROMPT_BYTES:
        sys.exit(f"runner prompt {order} is {size} bytes, over {MAX_PROMPT_BYTES}")
    (STAGE / "prompts" / f"judge-{order}.txt").write_text(prompt, encoding="utf-8")
    task = f"""Adjudicate unit X5 (items X5a and X5c).
Input file: {FINAL}/adjudication-inputs/x5.{order}.json
Packet file: {FINAL}/packets/x5.json
Repository root: {ROOT}

The input holds the question, the rules, the choices and, for each item, the packet item, Return A and Return B; the
packet holds the frozen packet both returns judged (its rules, each item's evidence and the primary sources). The
repository root is a plain export of commit {BASE_COMMIT}. Read only these two files and files under the root.
Return only this JSON: {{"leak": false, "leak_text": "", "items": [{{"id": "X5a" | "X5c", "choice": "A" | "B" |
"neither", "reasons": "...", "sources": [{{"locator": "...", "quote": "..."}}], "confidence": 0..1}}]}}, with exactly
one entry for X5a and one for X5c. If you find a leak, return {{"leak": true, "leak_text": "<the offending text>",
"items": []}} and stop.
"""
    (STAGE / "prompts" / f"claude-task-{order}.txt").write_text(task, encoding="utf-8")
    print(order, "runner prompt bytes", size, "input bytes", len(text.encode()))
old = json.loads((LANE / "adjudication-mapping-a.json").read_text())
if old != maps:
    sys.exit(f"attempt 2's mapping {maps} differs from attempt 1's {old}")
for p in sorted(STAGE.rglob("*")):
    if p.is_file():
        print(hashlib.sha256(p.read_bytes()).hexdigest()[:8], p.relative_to(STAGE))
print(json.dumps(maps))
