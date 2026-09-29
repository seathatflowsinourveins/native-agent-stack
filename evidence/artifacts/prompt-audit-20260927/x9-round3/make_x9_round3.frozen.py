"""Build X9's third adjudication round: round 2's attempt-2 judge files as sent, with K4's answer heads withheld as in
the published copies, plus round 2's outcome without family names and the executed comparison K5-K6
(x9-round3/prereg-r3.json, analysis-r3.json).

usage: make_x9_round3.py
Writes under <scratchpad>/j3/x9/, nested so that its parent directory lists nothing else:
  root/                                 plain export of main at ba1700ad, made before this script runs (git archive)
  adjudication-inputs/x9.{AB,BA}.json   round 2's inputs with the round-3 decision rule
  packets/x9.{AB,BA}.json               round 2's packets plus round_2, comparison_k5_k6 and the round-3 sources
  prompts/judge-{AB,BA}.txt             GPT-6 runner prompts, the same content inlined
  prompts/claude-task-{AB,BA}.txt       blind-adjudicator tasks
  schemas/judge.json                    round 2's schema, byte for byte
Round 3 keeps round 2's label assignment (x9-round2/attempt2-mapping.json), so round 2's relabelled sections are
reused unchanged. No judge is shown which lane wrote which text; x9-round3/round3-mapping.json records it here.
"""
import ast
import hashlib
import json
import re
import sys
from pathlib import Path

W3 = Path(__file__).resolve().parent
X3 = W3 / "x9-round3"
S = W3.parent
W2 = S / "convergence-prompt-audit"
X2 = W2 / "x9-round2"
J2 = S / "j2" / "x9"
OUT = S / "j3" / "x9"
ROOT = OUT / "root"
BASE = "ba1700ad"
MAX_PROMPT_BYTES = 120_000  # codex_job.py
sys.path.insert(0, str(X3))
import void_patterns_r3 as vp  # noqa: E402

# K4's withholding, taken from the round-2 packager itself (the same code that made the published copies).
tree = ast.parse((W2 / "package_x9_attempt2.py").read_text())
ns = {"re": re, "sys": sys}
for node in tree.body:
    if (isinstance(node, ast.Assign) and any(getattr(t, "id", "") in ("WITHHELD", "K4_ANSWER") for t in node.targets)) \
            or (isinstance(node, ast.FunctionDef) and node.name == "withhold_k4"):
        exec(compile(ast.Module([node], []), "package_x9_attempt2.py", "exec"), ns)
withhold_k4, WITHHELD = ns["withhold_k4"], ns["WITHHELD"]

mapping = json.loads((X2 / "attempt2-mapping.json").read_text())
prereg = json.loads((X3 / "prereg-r3.json").read_text())
analysis = json.loads((X3 / "analysis-r3.json").read_text())
metrics_doc = (X3 / "metrics_r3.py").read_text().split('"""')[1].split("Per run:\n", 1)[1].rstrip()
sources_r3 = {"questions": [q for q in json.loads((W3 / "sources-r3.json").read_text())["questions"]
                            if q["id"] in ("Q1", "Q2")]}  # the fixtures' sources; Q3-Q5 are not about X9
fixture_files = {rel: (X3 / "fixtures" / rel).read_text() for rel in prereg["fixture_files"]}
assert not (ROOT / ".git").exists() and (ROOT / "CLAUDE.md").read_text().startswith("@AGENTS.md\n")

HOST = [(re.compile(r"/tmp/claude-\d+/[^\s`'\")]*?/wt-x9r3-[gc0]"), "<worktree>"),
        (re.compile(r"/tmp/claude-\d+/[^\s`'\")]*?/x9-round3/fixtures"), "<fixtures>"),
        (re.compile(r"/tmp/claude-\d+/[^\s`'\")]*"), "<scratch>"), (re.compile(r"/home/[a-z0-9_-]+"), "~")]
CONFIG = re.compile(r"enabledPlugins|statusLine|status-?line (?:command|is wired|wiring)|installed_plugins"
                    r"|known_marketplaces|plugins/cache|[a-z0-9-]+@[a-z0-9-]+\"?\s*:\s*true")  # exposure_scan.py


def clean(s):
    for rx, sub in HOST:
        s = rx.sub(sub, s)
    if re.search(r"wt-x9r3-|/home/|scratchpad|/tmp/claude-", s):
        sys.exit(f"unsanitized text: {s[:120]}")
    return s


PRIVATE = re.compile(r"wt-x9r3?-|arms/|\barm[- ]?[gc0]\b|/tmp/|/home/|scratchpad|attempt1|runs/[gc0]/", re.I)


def private(s, where):
    hit = vp.MAPPING.search(s) or PRIVATE.search(s)
    if hit:
        sys.exit(f"{where}: path or mapping leak {hit.group(0)!r} near {s[max(0, hit.start() - 60):hit.end() + 60]!r}")
    return s


def blind(s, where):
    hit = re.search(r"gpt-?6|codex|openai", private(s, where), re.I)
    if hit:
        sys.exit(f"{where}: identity leak {hit.group(0)!r} near {s[max(0, hit.start() - 60):hit.end() + 60]!r}")
    return s


def names_for(order):
    m = mapping[order]
    return {m["A"]: "Return A's text", m["B"]: "Return B's text", "0": "current line (neither)"}


RULE9 = ("A text is applied when every adjudication in this round chooses it, and four 'neither' keep the current line. "
         "Otherwise the executed comparison K5-K6 decides between Return A's text and Return B's text by its "
         "preregistered order: fewer wrong statuses, then more correct statuses, then fewer non-answers, then the "
         "shorter text in o200k tokens. The current line is not a candidate there: all eight judgments of rounds 1 "
         "and 2 rejected it.")
ROUND2_RULE9 = ("The text is applied only when every adjudication in this round chooses it; otherwise the current line "
                "stays and both positions are recorded.")


def round2(order):
    n = names_for(order)
    g, c = n["g"], n["c"]
    return {"outcome": f"Round 2's four adjudications (two independent judges, each in both presentation orders, blind "
                       f"and audited clean) split two and two: two chose {g}, two chose {c}. None kept the current "
                       f"line. The texts were not applied.",
            "points": [f"Verification standard (the judgments that chose {g}): it separates listed availability from "
                       f"successful execution, since tools can be listed from the discovery cache before a server "
                       f"connects, and it covers plugin agents. They granted that {c} has the clearer fallback for "
                       f"unattended runs.",
                       f"Fallback (the judgments that chose {c}): 'report it as unconfirmed and name the command' "
                       f"gives a status whether or not anyone can answer, and CLAUDE.md also loads in headless runs "
                       f"and workflow children. They granted that {g} covers more, but the runs did not show that "
                       f"coverage changing behavior.",
                       "All four rejected the current line: the installed client refuses the commands it names "
                       "(C1, C2).",
                       "K1-K3 tied on their primary metric, and K4's premise did not hold, so the fallback was never "
                       "exercised. Round 2 named the comparison that would decide: headless and interactive sessions "
                       "on a component nothing in the session lists (a plugin with hooks only) and on an MCP server "
                       "whose tools are listed but which is not connected. K5-K6 below are its headless half."]}


COLS = ("wrong_status", "correct_status", "non_answer", "affirms", "denies", "says_unconfirmed", "question_only",
        "asks_user", "names_command", "called_target", "executed_target", "loaded_schema", "evidence_settings",
        "no_builtin_skill")


def method():
    c = prereg["client"]
    cases = "\n".join(f"  - {k['id']}: {k['question']} Fixture: {k['fixture']}. Truth: {k['truth']}."
                      for k in prereg["cases"])
    probes = "\n".join(f"  - {v}" for v in prereg["uncounted_probes"].values())
    return f"""Method (preregistered in full before the first counted run; the preregistration's sha256 is recorded):
- The same three worktrees of main at `{prereg['base'][:8]}` as K1-K4: identical except `CLAUDE.md`, which is
  `@AGENTS.md`, a blank line and one candidate text. Every other instruction, hook, plugin, MCP server and setting is
  the host's own and the same for all three.
- Claude Code {c['claude_code']} in headless mode (`claude -p`, stream-json), model `{c['model'].split(',')[0]}`
  passed on the command line and checked in every run's init event, permission mode and setting sources passed
  explicitly ({c['permission_mode'].split(',')[0]}; {c['setting_sources'].split(',')[0]}), at most {c['max_turns']}
  turns and {c['timeout_s']} s per run; run by promptfoo {prereg['harness']['promptfoo']} through a small exec script,
  one run at a time, {prereg['repetitions']} runs per question and text.
- Every run also loads two fixtures next to the host's own components (their files are below):
{cases}
- Ground truth is each run's own files: the hook's marker and the server's event log. Graders are deterministic code,
  no model grading. Per run:
{metrics_doc}
- non_answer (tertiary): no status and no closing question.
- Primary: wrong_status; secondary: correct_status; tertiary: non_answer; the rest describe behavior.
- Exclusions: {prereg['exclusions']}
- Uncounted probes before the preregistration was frozen:
{probes}
- Not tested: {'; '.join(prereg['untested'])}."""


def comparison(order):
    names = names_for(order)
    arms = [mapping[order]["A"], mapping[order]["B"], "0"]
    per = analysis["per_arm"]
    out = ["| text | runs | " + " | ".join(COLS) + " | total USD |", "|---|---" + "|---" * len(COLS) + "|---|"]
    for a in arms:
        t = per[a]
        out.append(f"| {names[a]} | {t['n']} | " + " | ".join(str(t["counts"][k]) for k in COLS)
                   + f" | {t['sum_cost_usd']} |")
    out += ["", "By question (runs; wrong_status; correct_status; non_answer; says_unconfirmed):", "",
            "| text | K5 | K6 |", "|---|---|---|"]
    for a in arms:
        pc = per[a]["per_case"]
        out.append(f"| {names[a]} | " + " | ".join(
            f"{pc[k]['n']}; {pc[k]['wrong_status']}; {pc[k]['correct_status']}; {pc[k]['non_answer']}; "
            f"{pc[k]['says_unconfirmed']}" for k in ("K5", "K6")) + " |")
    mo = analysis["metric_order"]
    if mo and mo.get("winner"):
        out += ["", f"By the preregistered order, {names[mo['winner']]} ranks first between the two returns, decided "
                    f"by {mo['decided_by']} (" + "; ".join(f"{s['metric']}: {names['g']} {s['g']}, {names['c']} "
                                                             f"{s['c']}" for s in mo["steps"]) + ")."]
    elif mo:
        out += ["", "By the preregistered order, the two returns tie on every step."]
    else:
        out += ["", "The comparison is incomplete under its exclusion rule and decides nothing."]
    out += ["", "USD is the client's own `total_cost_usd` estimate per run, descriptive only.", "",
            "Every run, in run order (tool calls in order, `!` marks a call whose result was an error; the run's "
            "fixture facts; the sentence the status was read from; the answer's first 240 characters; either text "
            "is withheld where the run read client settings files or the text quotes client configuration):", ""]
    withheld = 0
    for r in sorted(analysis["runs"], key=lambda r: r["transcript"]):
        flags = ", ".join(k for k in COLS if r[k])
        head, sent = clean(r["final_head"][:240]), clean(r["status_sentence"])
        if r["evidence_settings"] or CONFIG.search(r["final_head"]) or CONFIG.search(r["status_sentence"]):
            head, sent, withheld = WITHHELD, WITHHELD, withheld + 1
        fx = (f"hook marker lines {r['hook']['lines']}" if r["case"] == "K5"
              else f"init status {r['init_status']}; server events {r['mcp_events']}")
        out.append(f"- {names[r['arm']]}, {r['case']}: calls [{', '.join(r['calls'])}]; {fx}; true: {flags or 'none'}; "
                   f"status sentence: {json.dumps(sent, ensure_ascii=False)}; "
                   f"answer: {json.dumps(head, ensure_ascii=False)}")
    if analysis["excluded"]:
        out += ["", "Excluded runs (not rerun): " + "; ".join(f"{names[e['arm']]}, {e['case']}: {e['reason']}"
                                                            for e in analysis["excluded"])]
    out += ["", f"Both texts are withheld above for {withheld} runs.", "", "The fixtures' files:", ""]
    for rel, text in fixture_files.items():
        out += [f"`{rel}`:", "", "```", clean(text).rstrip("\n"), "```", ""]
    return "\n".join(out).rstrip("\n")


QUESTION = json.loads((J2 / "adjudication-inputs" / "x9.AB.json").read_text())["question"]
TASK_R2 = (J2 / "prompts" / "claude-task-AB.txt").read_text()
for d in ("adjudication-inputs", "packets", "prompts", "schemas"):
    (OUT / d).mkdir(parents=True, exist_ok=True)
(OUT / "schemas" / "judge.json").write_bytes((J2 / "schemas" / "judge.json").read_bytes())
sizes = {}
for order in ("AB", "BA"):
    inp = json.loads((J2 / "adjudication-inputs" / f"x9.{order}.json").read_text())
    assert inp["rules"][-1] == ROUND2_RULE9
    inp["rules"][-1] = RULE9
    inp_text = blind(json.dumps(inp, ensure_ascii=False, indent=1), f"input {order}")
    if re.search(r"\b(?:opus|sonnet|haiku|fable|mythos|astra)\b|\"(?:lane|model|provenance|refutation)\"", inp_text,
                 re.I):
        sys.exit(f"input {order}: a model name or reserved key")
    (OUT / "adjudication-inputs" / f"x9.{order}.json").write_text(inp_text + "\n")

    pkt = json.loads((J2 / "packets" / f"x9.{order}.json").read_text())
    pkt["comparison_k4"] = withhold_k4(pkt["comparison_k4"], f"packet {order}")
    r2 = round2(order)
    pkt["round_2"], pkt["round_2_points"] = r2["outcome"], r2["points"]
    pkt["comparison_k5_k6_method"], pkt["comparison_k5_k6"] = method(), comparison(order)
    pkt["sources"]["round3"] = sources_r3
    blind(json.dumps({k: v for k, v in pkt.items() if k != "sources"}, ensure_ascii=False), f"packet {order}")
    (OUT / "packets" / f"x9.{order}.json").write_text(
        private(json.dumps(pkt, ensure_ascii=False, indent=1), f"packet {order} with sources") + "\n")

    prompt2 = withhold_k4((J2 / "prompts" / f"judge-{order}.txt").read_text(), f"prompt {order}")
    head, _, _ = prompt2.partition("\n## Sources (round 1, round-1 supplement, round 2)\n")
    assert head.count(f"- {ROUND2_RULE9}") == 1
    head = head.replace(f"- {ROUND2_RULE9}", f"- {RULE9}").replace(str(J2), str(OUT))
    md_new = "\n".join(["", "## Round 2", "", r2["outcome"], "", "They turned on these points:", ""]
                       + [f"{i}. {p}" for i, p in enumerate(r2["points"], 1)]
                       + ["", "## New evidence 4: K5-K6, the headless half of the comparison round 2 named", "",
                          pkt["comparison_k5_k6_method"], "", pkt["comparison_k5_k6"]])
    src = "\n".join(["", "## Sources (round 1, round-1 supplement, round 2, round 3)", "", "```json",
                     json.dumps(pkt["sources"], ensure_ascii=False, indent=1), "```"])
    task_part, md_part = head.split("\n# Input\n", 1)
    blind(task_part.replace(str(ROOT), "<root>"), "task")
    prompt = task_part + "\n# Input\n" + blind(md_part, f"md {order}") + blind(md_new, f"md new {order}") \
        + private(src, f"sources {order}") + "\n"
    sizes[order] = len(prompt.encode())
    if sizes[order] > MAX_PROMPT_BYTES:
        sys.exit(f"runner prompt {order} is {sizes[order]} bytes, over {MAX_PROMPT_BYTES}")
    (OUT / "prompts" / f"judge-{order}.txt").write_text(prompt)
    task = (J2 / "prompts" / f"claude-task-{order}.txt").read_text().replace(str(J2), str(OUT))
    if vp.MAPPING.search(task + prompt):
        sys.exit(f"task or prompt {order}: mapping string")
    (OUT / "prompts" / f"claude-task-{order}.txt").write_text(task)
    print(order, "A =", mapping[order]["A"], "prompt bytes", sizes[order])
(X3 / "round3-mapping.json").write_text(json.dumps(mapping, indent=1) + "\n")
print(json.dumps({f"{d}/{f.name}": hashlib.sha256(f.read_bytes()).hexdigest()[:12]
                  for d in ("adjudication-inputs", "packets", "prompts", "schemas") for f in sorted((OUT / d).iterdir())}))
