"""Build lane A's final X5c adjudication in the blind-adjudicator contract's format (.claude/agents/blind-adjudicator.md),
after build_root_final.py: one JSON input per presentation order under adjudication-inputs/, one JSON packet under
packets/, the Codex-strict schema, the runner prompts and the blind-adjudicator tasks. Attempt 2's
make_adjudication_a2.py for the final round's split on X5c, with both effective resolutions stated the same way
(line 3, tree, diff, co-changes and the coordinator's measured checks).

usage: build_adjudication_final.py
<scratchpad>/j7/x5c/
  root/                              build_root_final.py; this script adds root/packet.md (the packet text, so a
                                     return's packet.md:N locator resolves)
  adjudication-inputs/x5c.{AB,BA}.json
  packets/x5c.json                   the final round's frozen packet (text and sha256)
  schemas/adjudicate.json
  prompts/judge-{AB,BA}.txt          runner prompts (input and packet inlined)
  prompts/claude-task-{AB,BA}.txt    blind-adjudicator tasks
  runs/                              the runner's work directory, created at dispatch
The mapping is written to adjudication-mapping-final.json here, never under j7.
"""
import hashlib
import json
import random
import re
import sys
from pathlib import Path

AD = Path(__file__).resolve().parent
A2 = AD.parent
W3 = A2.parent
HOLD = W3.parent
S = HOLD.parent
K2_SENT = S / "k2"  # where the lanes read it; moved to HOLD / "k2" before this adjudication
K2 = HOLD / "k2"
J7 = S / "j7" / "x5c"
ROOT = J7 / "root"
MAX_PROMPT_BYTES = 120_000  # codex_job.py
BASE_COMMIT = "8315274f"
TEMPLATE = "adoption/templates/codex.AGENTS.template.md"
TEST = "tests/test_codex_worker_lane.py"

packet = (K2 / "packets" / "packet.md").read_text(encoding="utf-8")
PSHA = hashlib.sha256(packet.encode()).hexdigest()
if PSHA != (K2 / "packets" / "packet.sha256").read_text().split()[0]:
    sys.exit("packet.md changed after freezing")
returns = {k: {i["id"]: i for i in json.loads((A2 / "returns" / f"{k}.json").read_text())["items"]}
           for k in ("gpt6", "claude")}
tally = json.loads((A2 / "tally-final.json").read_text())
assert tally["items"]["X5c"]["outcome"].startswith("adjudicate") and not tally["void"]
assert tally["items"]["X5a"]["outcome"] == "apply the proposed change"
lanes = {"g": returns["gpt6"]["X5c"], "c": returns["claude"]["X5c"]}
assert lanes["g"]["verdict"] == "agree" and lanes["c"]["verdict"] == "amend"

SUBS = [(str(K2_SENT / "root") + "/", ""), (str(K2_SENT / "packets" / "packet.md"), "packet.md")]
IDENTIFYING = re.compile(r"/tmp/|/home/|scratchpad|claude-brief|gpt6|gpt-|brief line|\bbrief\b|lane-a|convergence-r3"
                         r"|<session-id>|<user>|codex exec|\bopus\b|sonnet|haiku|fable|mythos|astra|\bo3\b|\bo4\b"
                         r"|anthropic|openai|\"(?:lane|model|provenance|refutation)\":", re.I)
# the blind-adjudicator's own leak list, run over the whole input
LEAK = re.compile(r"\"(?:lane|model|provenance|refutation)\"\s*:|gpt-|\bo3\b|\bo4\b|astra|gpt-6-(?:sol|luna)"
                  r"|gpt-5\.6-terra|\bopus\b|sonnet|haiku|fable|mythos|claude-opus"
                  r"|\b(?:codex|claude|gpt-?6)(?:'s)?[- ](?:lane|proposal|return|reviewer|amendment)s?\b"
                  r"|(?:^|[\s\"'(`])(?:/tmp/|/home/|/Users/|~/)", re.I | re.M)
KNOWN_LEAK_LIST_HITS = {"~/"}  # `~/.claude/CLAUDE.md` in the packet's rules, as in attempt 2's input


def scrub(text):
    for old, new in SUBS:
        text = text.replace(old, new)
    return text


def section(item_id):
    m = re.search(rf"^## {item_id}: .*?(?=^---$|\Z)", packet, re.S | re.M)
    if not m:
        sys.exit(f"no packet section for {item_id}")
    return m.group(0).rstrip()


def packet_rules():
    start = packet.index("You are an independent reviewer.")
    return packet[start:packet.index("\n---\n", start)].rstrip()


def logged(path, rx):
    return [ln for ln in Path(path).read_text().splitlines() if re.search(rx, ln)]


SUMMARY = r"^(Ran |OK|FAILED|FAIL:|ERROR:|AssertionError)"
PIN = "tests.test_codex_worker_lane.TemplateTests.test_top_rule_and_upstream_text_are_verbatim"
TARGETED = ("tests.test_install_claude_profile tests.test_codex_worker_lane tests.test_codex_agents "
            "tests.test_codex_lane tests.test_landscape_sweep_harness tests.test_adoption_docs_consistency")


def check(label, cmd, log, rx, code):
    return {"check": label, "command": cmd, "exit_code": code, "output_lines": logged(log, rx)}


MEASURED = {
    "g": [
        check("line 3 set to this text, tests/test_codex_worker_lane.py at the base pin (no re-pin)",
              f"python3 -B -m unittest {PIN}", W3 / "x5c-control-template-only.log", SUMMARY, 1),
        check("the same with the re-pinned test", f"python3 -B -m unittest {PIN}", W3 / "x5c-control-repinned.log",
              SUMMARY, 0),
        check("template and test changed, manifest not yet re-registered", "python3 scripts/validate.py",
              W3 / "x5c-validate-before-registration.log", r"\S", 1),
        check("after registering the changed files (with X5a's)", "python3 scripts/validate.py",
              A2 / "x5a-validate-after-registration.log", r"\S", 0),
        check("the complete change (proposed/): the test modules that read either template or the pin",
              f"python3 -B -m unittest {TARGETED}", A2 / "x5-proposal-targeted-tests.log", r"^(Ran |OK|FAILED)", 0)],
    "c": [
        check("line 3 set to this text, tests/test_codex_worker_lane.py at the other text's pin (no re-pin)",
              f"python3 -B -m unittest {PIN}", AD / "x5c-amend-control-template-only.log", SUMMARY, 1),
        check("the same with the re-pinned test", f"python3 -B -m unittest {PIN}", AD / "x5c-amend-repinned.log",
              SUMMARY, 0),
        check("template and test changed, manifest not yet re-registered", "python3 scripts/validate.py",
              AD / "x5c-amend-validate-before-registration.log", r"\S", 1),
        check("after registering the changed files (X5a's already registered)", "python3 scripts/validate.py",
              AD / "x5c-amend-validate-after-registration.log", r"\S", 0),
        check("the complete change (amended/): the test modules that read either template or the pin",
              f"python3 -B -m unittest {TARGETED}", AD / "x5c-amend-targeted-tests.log", r"^(Ran |OK|FAILED)", 0)]}
TREE = {"g": ("proposed/", "proposal.diff"), "c": ("amended/", "amendment.diff")}


def facts(key):
    tree, diff = TREE[key]
    tpl = (ROOT / tree / TEMPLATE).read_bytes()
    line3 = tpl.decode().split("\n")[2]
    test = (ROOT / tree / TEST).read_text()
    sha = re.search(r'^TOP_RULE_SHA256 = "([0-9a-f]{64})"', test, re.M).group(1)
    words = int(re.search(r"self\.assertEqual\(len\(top\.split\(\)\), (\d+)\)", test).group(1))
    return line3, len(tpl), sha, words


def effective(key):
    r = lanes[key]
    tree, diff = TREE[key]
    line3, nbytes, sha, words = facts(key)
    if r["verdict"] == "agree":
        summary = ("Agrees with the packet's proposed text for this item, exactly as written in the item, applied "
                   "with the co-changes the packet lists.")
        assert line3 == section("X5c").split("Proposed text: ", 1)[1].split("\n", 1)[0]
    else:
        summary = ("Replacement (verbatim) of line 3, applied with the co-changes its reasons name, recomputed by the "
                   "packet's procedure.")
        assert line3 == r["resolution_text"].strip()
    return {"verdict": r["verdict"],
            "effective_resolution": {
                "summary": summary, "line_3": line3, "tree": tree, "diff": diff,
                "co_changes": (f"{TEST}: TOP_RULE_SHA256 (:47) set to {sha}, the word count at :210 and the :45 "
                               f"comment set to {words}, both computed with the test module's own "
                               f"template_segments(); manifests/evidence.json: the template and the test "
                               f"re-registered (docs/lanes.md:96-128); host step, outside the repository: re-run "
                               f"tools/adoption/apply_codex_lane.py (dry run, then --apply) where the lane block is "
                               f"installed."),
                "line_3_words": len(line3.split()), "template_bytes": nbytes, "top_rule_block_words": words,
                "coordinator_measurements": MEASURED[key]},
            "reasons": scrub(r["reasons"]),
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

v_prop = json.loads((AD / "withheld-check.json").read_text())
REPO_ROOT = (
    f"Under the repository root: base/ is main at {BASE_COMMIT}, a plain export without git history; proposed/ is base/ "
    "with the packet's complete proposal (X5a and X5c with their co-changes); amended/ is base/ with X5a as proposed "
    "and X5c as the amending return's line 3, with the co-changes that return names, recomputed and applied by the "
    "coordinator; proposal.diff and amendment.diff are those two trees' diffs against base/; packet.md is the packet "
    "text of the packet file, so a return's packet.md:N locator resolves there. Withheld from all three trees: "
    + " and ".join(v_prop["withheld"]) + ", which record earlier review rounds of this audit by reviewer. Because of "
    f"that, scripts/validate.py run in proposed/ or amended/ reports {v_prop['missing_entries']} manifest entries as "
    "'file missing', all under those two paths and nothing else (measured in copies of both trees); the test modules "
    f"in the measured checks pass in both copies ({v_prop['targeted']}), with "
    f"{v_prop['extra_skips']} more tests skipped than in a git worktree because the trees have no git history. "
    "The coordinator's measured checks were run in a full git worktree.")
CONTEXT = [
    "X5a, the packet's other item, is not in dispute: both reviews agreed with its proposed text, so it is applied as "
    "proposed, and proposed/ and amended/ both include it.",
    "Each return's coordinator_measurements were run by the coordinator, not by that return's reviewer; they are "
    "listed the same way for both returns."]
rng = random.Random("lane-a-final-x5c-20260928")
g_first = rng.random() < 0.5
mapping = {}
for d in ("adjudication-inputs", "packets", "schemas", "prompts"):
    (J7 / d).mkdir(parents=True, exist_ok=True)
(ROOT / "packet.md").write_text(packet, encoding="utf-8")
packet_json = json.dumps({"packet_sha256": PSHA, "base": BASE_COMMIT, "packet": packet}, ensure_ascii=False,
                         indent=1) + "\n"
(J7 / "packets" / "x5c.json").write_text(packet_json, encoding="utf-8")
schema = json.loads((W3 / "lane-a" / "adj" / "schema-adjudicate.json").read_text())
schema["properties"]["items"]["items"]["properties"]["id"]["enum"] = ["X5c"]
(J7 / "schemas" / "adjudicate.json").write_text(json.dumps(schema, indent=1) + "\n")
for order, first_g in (("AB", g_first), ("BA", not g_first)):
    a, b = ("g", "c") if first_g else ("c", "g")
    mapping[order] = {"X5c": {"A": a, "B": b}}
    doc = {"unit": "X5c", "items_in_unit": ["X5c"],
           "question": ("Two independent reviews judged the same frozen packet (the packet file, sha256 " + PSHA +
                        ") and disagreed on item X5c. Choose the return whose effective resolution the evidence "
                        "supports better, or neither."),
           "repository_root": REPO_ROOT, "context": CONTEXT,
           "choices": {"A": "apply Return A's effective resolution exactly as written",
                       "B": "apply Return B's effective resolution exactly as written",
                       "neither": "the current text stays unchanged"},
           "rules": RULES, "packet_rules_verbatim": packet_rules(),
           "items": [{"id": "X5c", "packet_item": section("X5c"), "return_A": effective(a),
                      "return_B": effective(b)}]}
    text = json.dumps(doc, ensure_ascii=False, indent=1) + "\n"
    rets = json.dumps([doc["items"][0][k] for k in ("return_A", "return_B")], ensure_ascii=False)
    m = IDENTIFYING.search(rets)
    if m:
        sys.exit(f"{order}: identifying text remains: {rets[max(0, m.start() - 60):m.end() + 60]!r}")
    found = {}
    for mm in LEAK.finditer(text):
        found.setdefault(mm.group(0).strip(" \"'(`").lower(), text[max(0, mm.start() - 60):mm.end() + 60])
    unknown = {k: w for k, w in found.items() if k not in KNOWN_LEAK_LIST_HITS}
    if unknown:
        sys.exit(f"{order}: leak-list hits in the input: {unknown}")
    (J7 / "adjudication-inputs" / f"x5c.{order}.json").write_text(text, encoding="utf-8")
    prompt = (f"Task: adjudicate unit X5c (one item, X5c) and answer only in the required JSON, one entry for X5c. "
              f"The input and the packet are below. The original files are under the read-only repository root "
              f"{ROOT}: base/, proposed/, amended/, proposal.diff, amendment.diff and packet.md; read them there (for "
              f"example sed -n, rg, diff -u; python3 -B runs a test module against a copy without writing). Do not "
              f"write, install or change anything. You may search the web for current official documentation; cite "
              f"official sources only.\n\n# Input file (x5c.{order}.json)\n\n```json\n{text}```\n\n"
              f"# Packet file (x5c.json)\n\n```json\n{packet_json}```\n")
    size = len(prompt.encode())
    if size > MAX_PROMPT_BYTES:
        sys.exit(f"runner prompt {order} is {size} bytes, over {MAX_PROMPT_BYTES}")
    (J7 / "prompts" / f"judge-{order}.txt").write_text(prompt, encoding="utf-8")
    task = f"""Adjudicate unit X5c (one item, X5c).
Input file: {J7}/adjudication-inputs/x5c.{order}.json
Packet file: {J7}/packets/x5c.json
Repository root: {ROOT}

The input holds the question, the rules, the choices and, for the item, the packet item, Return A and Return B, each
with its effective resolution; the packet holds the frozen packet both returns judged. Under the repository root,
base/ is main at {BASE_COMMIT}, proposed/ and amended/ are base/ with each resolution applied, proposal.diff and
amendment.diff are their diffs, and packet.md is the packet text. Read only these two files and files under the root.
You cannot run commands; the measured checks in the input were run by the coordinator, and you check them against
the files.
Return only this JSON: {{"leak": false, "leak_text": "", "items": [{{"id": "X5c", "choice": "A" | "B" | "neither",
"reasons": "...", "sources": [{{"locator": "...", "quote": "..."}}], "confidence": 0..1}}]}}, with exactly one entry,
for X5c. If you find a leak, return {{"leak": true, "leak_text": "<the offending text>", "items": []}} and stop.
"""
    (J7 / "prompts" / f"claude-task-{order}.txt").write_text(task, encoding="utf-8")
    print(order, "runner prompt bytes", size, "input bytes", len(text.encode()), "leak-list hits", sorted(found))
(AD / "adjudication-mapping-final.json").write_text(json.dumps(
    {"seed": "lane-a-final-x5c-20260928", "g": "the GPT-6 lane's return (returns/gpt6.json, agree)",
     "c": "the Claude lane's return (returns/claude.json, amend)", "orders": mapping}, indent=1) + "\n")
for p in sorted(J7.rglob("*")):
    if p.is_file() and "root" not in p.relative_to(J7).parts[:1]:
        print(hashlib.sha256(p.read_bytes()).hexdigest()[:8], p.relative_to(J7))
print("root/packet.md", hashlib.sha256((ROOT / "packet.md").read_bytes()).hexdigest()[:8])
