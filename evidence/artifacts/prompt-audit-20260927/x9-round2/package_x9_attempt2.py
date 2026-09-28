"""Copy X9's second round (comparison K1-K4, void attempt 1, final attempt 2) into the PR-2 worktree as evidence.

usage: package_x9_attempt2.py
Target: <wt-pa-pr2>/evidence/artifacts/prompt-audit-20260927/x9-round2/. Harness, arms and K4 files are copied byte
for byte, so the sha256 maps in prereg.json and k4/prereg-k4.json still hold; the two promptfoo configs name the
harness directory by its host path and are copied with that path replaced (their preregistered hashes are of the files
as run). Raw session transcripts are not copied: they hold the host's init data and tool results from client
configuration files. promptfoo's results files are kept in a compact form without row ids. The attempt-1 audit
self-test keeps each hit's pattern, scope and match, not the surrounding text. Refuses to write a file that still
holds a host path, a home directory, a UUID or an e-mail address.
Revised 2026-09-28 after review: also writes the K1-K3 run window, the settings file names per run, the K4 skill-list
sentences, the isolation receipt, a source supplement, the retally script and the live-only grep diagnostic.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parent
S = WORK.parent
X = WORK / "x9-round2"
J = S / "j2" / "x9"
A1RUNS = S / "prompt-audit-x9-round2-runs"
A1JUDGE = S / "prompt-audit-x9-round2-judgment"
OUT = S / "wt-pa-pr2" / "evidence" / "artifacts" / "prompt-audit-20260927" / "x9-round2"
SUBS = sorted([(str(J / "root"), "<root>"), (str(J), "<attempt2>"), (str(S / "wt-x9r2-base"), "<attempt1-root>"),
               (str(A1JUDGE), "<attempt1-judgment>"), (str(A1RUNS), "<attempt1-runs>"), (str(X), "<x9>"),
               (str(WORK), "<work>"), (str(S / "wt-x9-g"), "<worktree>"), (str(S / "wt-x9-c"), "<worktree>"),
               (str(S / "wt-x9-0"), "<worktree>"), (str(S / ".hold"), "<hold>"), (str(S), "<scratch>"),
               (str(S.parent), "<session>"), (str(Path.home() / ".claude" / "projects"), "<projects>"),
               (f"{S.parent.parent.name}/{S.parent.name}", "<project-dir>/<session-id>")],
              key=lambda p: -len(p[0]))
# Real host paths only (a script's own regex text such as r"/home/[a-z0-9_-]+" is not one): the host scratch root,
# a flattened home path in a project directory name, a home directory with a name, a UUID and an e-mail address.
PRIVATE = re.compile(r"/tmp/claude-\d+|-home-[A-Za-z0-9_]+-|/(?:home|Users)/[A-Za-z0-9_.-]+"
                     r"|[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}", re.I)
RUNNER_KEYS = ("status", "exit", "started", "finished", "usage", "usage_status", "limit", "limit_marker", "model",
               "effort", "codex_version", "attempts")


def clean(text):
    for old, new in SUBS:
        text = text.replace(old, new)
    return re.sub(r"/home/[A-Za-z0-9_.-]+", "~", text)


def write(name, text, verbatim=False):
    if not verbatim:
        text = clean(text)
    hits = [m.group(0) for m in PRIVATE.finditer(text) if m.group(0) != "noreply@anthropic.com"]
    if hits:
        sys.exit(f"{name}: private content left: {sorted(set(h[:24] for h in hits))[:5]}")
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if verbatim:
        path.write_bytes(text.encode())
    else:
        path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1)


def events(path):
    for line in path.read_text().splitlines():
        try:
            yield json.loads(line)
        except ValueError:
            continue


# K4's answer heads quote the host's client configuration (enabled-plugin entries, status-line wiring, plugin install
# records), which evidence must not carry (AGENTS.md). They are withheld wherever they appear: the packets and prompts
# as sent (sent-sha256.json keeps the originals' hashes), k4/analysis-k4.json and k4/results-k4-compact.json. Each
# answer's first sentence is kept. Added 2026-09-28 after the advisor's review of the published files.
WITHHELD = "[withheld in the published copy: this answer head quotes client configuration files]"
K4_ANSWER = re.compile(r'(; first sentence: ".*?"; answer: )".*"$', re.M)


def withhold_k4(text, where):
    out, n = K4_ANSWER.subn(lambda m: m.group(1) + WITHHELD, text)
    if n != 9:
        sys.exit(f"{where}: expected 9 K4 answer heads to withhold, found {n}")
    return out


def facts(output, head, withhold=False):
    """summarize.py's facts without host configuration text: the answer is cut to the head the analysis keeps (or
    withheld for K4), and Bash command strings (which named and printed client settings files in K2 and K4) are
    dropped."""
    s = json.loads(output)
    init = s.get("init") or {}
    return {**{k: s.get(k) for k in ("arm", "transcript", "exit", "duration_ms", "result_subtype", "num_turns",
                                     "cost_usd", "usage")},
            "init": {"version": init.get("version"), "model": init.get("model"),
                     "permission_mode": init.get("permission_mode"), "mcp_servers": init.get("mcp_servers"),
                     "plugins": init.get("plugins")},
            "calls": [{k: c.get(k) for k in ("name", "skill", "query", "is_error")} for c in s.get("calls") or []],
            "final_head": WITHHELD if withhold else (s.get("final") or "")[:head]}


def compact(results_path, head, withhold=False):
    res = json.loads(results_path.read_text())
    rows = [{"provider": r["provider"].get("label"), "vars": {k: r["vars"][k] for k in ("case", "target")
                                                              if k in r["vars"]},
             "latency_ms": r.get("latencyMs"),
             "assertions": {c["assertion"]["metric"]: c["pass"] for c in r["gradingResult"]["componentResults"]},
             "output": facts(r["response"]["output"], head, withhold)} for r in res["results"]["results"]]
    return rows, {"harness": res["metadata"], "eval_id": res["evalId"], "runtime_options": res.get("runtimeOptions"),
                  "stats": res["results"]["stats"], "rows": rows}


def provider_usage(rows):
    return {a: {k: sum((row["output"].get("usage") or {}).get(k) or 0 for row in rows if row["provider"] == f"arm-{a}")
                for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")}
            for a in ("g", "c", "0")}


OUT.mkdir(parents=True, exist_ok=True)
# K1-K3: preregistration, harness and arms byte for byte (prereg.json's sha256 must still hold).
for name in ("prereg.json", "prereg.sha256", "run_arm.sh", "summarize.py", "metrics.py", "analyze.py",
             "arms/CLAUDE.g.md", "arms/CLAUDE.c.md", "arms/CLAUDE.0.md", "arms/gpt6.txt", "arms/claude.txt"):
    write(name, (X / name).read_text(), verbatim=True)
write("promptfooconfig.yaml", (X / "promptfooconfig.yaml").read_text())
write("eval.log", (X / "eval.log").read_text())
write("analysis.json", (X / "analysis.json").read_text())
write("run-window.json", dump({"started": (X / "run.started").read_text().strip(),
                               "finished": (X / "run.finished").read_text().strip()}))
rows, doc = compact(X / "results.json", 240)
write("results-compact.json", dump(doc))
# K4, the same way.
for name in ("prereg-k4.json", "prereg-k4.sha256", "metrics_k4.py", "analyze_k4.py"):
    write(f"k4/{name}", (X / "k4" / name).read_text(), verbatim=True)
write("k4/promptfooconfig-k4.yaml", (X / "k4" / "promptfooconfig-k4.yaml").read_text())
write("k4/eval-k4.log", (X / "k4" / "eval-k4.log").read_text())
analysis4 = json.loads((X / "k4" / "analysis-k4.json").read_text())
for run in analysis4["runs"]:
    run["final_head"] = WITHHELD
write("k4/analysis-k4.json", dump(analysis4))
write("k4/run-window.json", dump({"started": (X / "k4" / "run.started").read_text().strip(),
                                  "finished": (X / "k4" / "run.finished").read_text().strip()}))
rows4, doc4 = compact(X / "k4" / "results-k4.json", 400, withhold=True)
write("k4/results-k4-compact.json", dump(doc4))
write("k4/skill-list-mentions.json", (X / "k4" / "skill-list-mentions.json").read_text())
write("k4/k4_mentions.py", (WORK / "k4_mentions.py").read_text())
# Review round: the settings file names each run's Bash commands named (the command text itself is dropped above).
write("settings-reads.json", (X / "settings-reads.json").read_text())
write("settings_reads.py", (WORK / "settings_reads.py").read_text())
write("isolation-receipt.json", (X / "isolation-receipt.json").read_text())
write("isolation_receipt.py", (WORK / "isolation_receipt.py").read_text())

# Uncounted probes: facts only, never the raw transcript.
probe = {"version": None, "model": None, "calls": []}
results = {}
for e in events(X / "probe" / "probe-skill-builtins.jsonl"):
    if e.get("type") == "system" and e.get("subtype") == "init":
        probe["version"], probe["model"] = e.get("claude_code_version"), e.get("model")
    elif e.get("type") == "assistant":
        probe["calls"] += [{"id": c["id"], "name": c["name"], "input": c.get("input")}
                           for c in e["message"]["content"] if c.get("type") == "tool_use"]
    elif e.get("type") == "user" and isinstance(e["message"].get("content"), list):
        results.update({c["tool_use_id"]: {"is_error": c.get("is_error"), "text": c.get("content")}
                        for c in e["message"]["content"] if c.get("type") == "tool_result"})
    elif e.get("type") == "result":
        probe["final"] = e.get("result")
for c in probe["calls"]:
    c["result"] = results.get(c.pop("id"))
probe["prompt"] = ("Diagnostic probe for a client-capability check. Call the Skill tool exactly twice: first with skill "
                   "\"context\", then with skill \"mcp\". Do not call any other tool. Then report, for each call, whether "
                   "the tool result was an error and the first 200 characters of the result text.")
write("probe/skill-builtins.json", dump(probe))
init = next(e for e in events(X / "probe" / "probe-0.jsonl") if e.get("type") == "system" and e.get("subtype") == "init")
names = lambda xs: sorted(x if isinstance(x, str) else x.get("name") for x in xs)  # noqa: E731
BUILTINS = ("mcp", "context", "plugin", "plugins", "reload-plugins")
write("probe/init-lists.json", dump({
    "note": "C4's facts from the init event of a headless session of the base: counts and the built-in commands in "
            "question, not the host's full command and skill lists.",
    "version": init.get("claude_code_version"), "model": init.get("model"), "permission_mode": init.get("permissionMode"),
    "checked": list(BUILTINS),
    "mcp_servers": {s["name"]: s["status"] for s in init["mcp_servers"]}, "plugins": names(init["plugins"]),
    "slash_commands": {"count": len(init["slash_commands"]),
                       "present": [b for b in BUILTINS if b in names(init["slash_commands"])]},
    "terminal_slash_commands": names(init["terminal_slash_commands"]),
    "skills": {"count": len(init["skills"]), "present": [b for b in BUILTINS if b in names(init["skills"])]}}))
write("sources-round2.json", (X / "sources-round2.json").read_text())
write("package_x9_attempt2.py", Path(__file__).read_text())
PAGE = S / "pages" / "skills.md"
QUOTE = "Custom commands have been merged into skills."
line16 = PAGE.read_text().splitlines()[15]
assert f"**{QUOTE}**" in line16, "the skills page's line 16 no longer holds the quote"
write("sources-supplement.json", dump({
    "note": "A source the packets' K4 section cites (x9.AB.json and x9.BA.json, comparison_k4) that sources-round2.json "
            "does not hold; recorded after review from the page as fetched for the packets.",
    "sources": [{"id": "SUP1", "url": "https://code.claude.com/docs/en/skills.md",
                 "retrieved": __import__("datetime").datetime.fromtimestamp(
                     PAGE.stat().st_mtime, __import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "locator": "line 16 of the Markdown page as fetched (the quote is bold there)",
                 "page_sha256": __import__("hashlib").sha256(PAGE.read_bytes()).hexdigest(),
                 "quote": QUOTE, "line": line16.strip()}]}))

# Attempt 1: void, recorded before any Claude choice was seen; its returns are kept, not counted.
write("attempt1/void.json", (X / "attempt1-void.json").read_text())
write("attempt1/mapping.json", (X / "attempt1" / "judgment-mapping.json").read_text())
for name in ("gpt6-AB.json", "gpt6-BA.json", "claude-AB.json"):
    write(f"attempt1/{name}", (X / "attempt1" / name).read_text())
selftest = json.loads((X / "audit-selftest-attempt1.json").read_text())
# The Claude A/B judgment's windows are kept (from its input path or record path on, the host prefix cut) so the
# README's reading of its hits can be checked; a window without one of these anchors is refused by write().
ANCHOR = re.compile(r"^.*?(?=docs/decisions/|\"output_mode\"|prompt-audit-x9-round2-judgment)", re.S)
write("attempt1/audit-selftest.json", dump({
    "note": "audit_attempt2.py run on attempt 1's four transcripts before any attempt-2 return was read; each hit's "
            "pattern, scope and match. The audit's text windows are kept only for claude-AB, from the judgment's "
            "input directory, the Grep options or the record path on (added after review).",
    "patterns_sha256": selftest["patterns_sha256"],
    "judgments": {k: {"void": r["void"], "hits": sorted({(h["pattern"], h["scope"], h["match"]) for h in r["hits"]}),
                      **({"windows": sorted({(h["pattern"], h["scope"], ANCHOR.sub("", h["window"]))
                                             for h in r["hits"]})} if k == "claude-AB" else {}),
                      "items": r["items"]} for k, r in selftest["judgments"].items()}}))

# Attempt 2: the builder, its inputs and outputs, the audit and the tally.
for name in ("make_x9_attempt2.py", "check_orders.py", "audit_attempt2.py", "tally_attempt2.py", "retally.py",
             "claude_usage.py", "judge_actions.py", "gpt6_workdir_rg.py", "gpt6_workdir_liveonly.py", "root_scan.py"):
    write(f"attempt2/{name}", (WORK / name).read_text())
write("attempt2/void_patterns.py", (X / "void_patterns.py").read_text(), verbatim=True)
# The first check_orders.py, run before dispatch; recovered verbatim from the coordinator's session log (its Write at
# 2026-09-28T03:07:47Z, no edit after it) with recover_write.py.
write("attempt2/check_orders_first.py", (WORK / "check_orders_first.py").read_text(), verbatim=True)
write("attempt2/mapping.json", (X / "attempt2-mapping.json").read_text())
write("attempt2/schemas/judge.json", (J / "schemas" / "judge.json").read_text())
for order in ("AB", "BA"):
    write(f"attempt2/inputs/x9.{order}.json", (J / "adjudication-inputs" / f"x9.{order}.json").read_text())
    pkt = json.loads((J / "packets" / f"x9.{order}.json").read_text())
    pkt["comparison_k4"] = withhold_k4(pkt["comparison_k4"], f"packet {order}")
    write(f"attempt2/packets/x9.{order}.json", json.dumps(pkt, ensure_ascii=False, indent=1))
    write(f"attempt2/prompts/judge-{order}.txt",
          withhold_k4((J / "prompts" / f"judge-{order}.txt").read_text(), f"prompt {order}"))
    write(f"attempt2/prompts/claude-task-{order}.txt", (J / "prompts" / f"claude-task-{order}.txt").read_text())
    r = json.loads((J / "runs" / f"x9r2-judge-{order}.runner.json").read_text())
    write(f"attempt2/gpt6.{order}.json", dump({"lane": "GPT-6 packaged runner (codex_call.sh start/result)",
                                               "runner": {k: r[k] for k in RUNNER_KEYS if k in r},
                                               "return": json.loads(r["output_text"])}))
usage2 = json.loads((X / "claude-usage-attempt2.json").read_text())
for order in ("AB", "BA"):
    write(f"attempt2/claude.{order}.json", dump({
        "lane": "Claude Agent tool, blind-adjudicator (frontmatter model opus, effort max; Read, Glob and Grep only)",
        "usage": usage2[f"judge-{order}"], "return": json.loads((X / "returns2" / f"claude-{order}.json").read_text())}))
audit = json.loads((X / "audit-attempt2.json").read_text())
write("attempt2/audit.json", dump(audit))
write("attempt2/tally.json", (X / "tally-attempt2.json").read_text())
write("attempt2/judge-actions.json", (X / "judge-actions-attempt2.json").read_text())
write("attempt2/gpt6-workdir.txt", (X / "gpt6-workdir-attempt2.txt").read_text())
write("attempt2/gpt6-workdir-liveonly.txt", (X / "gpt6-workdir-liveonly-attempt2.txt").read_text())
write("attempt2/root-scan.txt", (X / "root-scan-attempt2.txt").read_text())
sent = {}
for d in ("adjudication-inputs", "packets", "prompts", "schemas"):
    for f in sorted((J / d).iterdir()):
        sent[f"{d}/{f.name}"] = __import__("hashlib").sha256(f.read_bytes()).hexdigest()
write("attempt2/sent-sha256.json", dump({
    "note": "sha256 of each attempt-2 file as the judges received it. The inputs and schema are published byte for "
            "byte. The packets and the two judge prompts are published with K4's nine answer heads withheld, because "
            "they quote client configuration files; the four prompt files also carry the host path of the repository "
            "root, which the published copies replace with <root> or <attempt2>. Only these recorded hashes cover "
            "the originals.",
    "files": sent}))

usage1 = json.loads((X / "claude-usage-round2.json").read_text())
probe_runner = json.loads((A1RUNS / "gpt6-probe.runner.json").read_text())
runner = lambda p: {k: v for k, v in json.loads(p.read_text()).items() if k in ("status", "exit", "limit", "usage")}  # noqa: E731
write("usage.json", dump({
    "note": "Provider usage of X9's second round, including the void attempt 1. Anthropic usage fields are disjoint and "
            "listed side by side, never added; each Codex runner record is its own. The comparison's cost is the "
            "client's per-run total_cost_usd estimate. The coordinator session is not included.",
    "claude_agents": {"attempt1": usage1, "attempt2": usage2},
    "gpt6_runner": {"attempt1": {"probe": runner(A1RUNS / "gpt6-probe.runner.json"),
                                 **{f"judge-{o}": runner(A1RUNS / f"x9r2-judge-{o}.runner.json") for o in ("AB", "BA")}},
                    "attempt2": {f"judge-{o}": runner(J / "runs" / f"x9r2-judge-{o}.runner.json")
                                 for o in ("AB", "BA")}},
    "comparison_runs": {
        "k1_k3": {a: {"runs": t["n"], "sum_cost_usd": t["sum_cost_usd"], "provider_usage": provider_usage(rows)[a]}
                  for a, t in json.loads((X / "analysis.json").read_text())["per_arm"].items()},
        "k4": {a: {"runs": t["n"], "sum_cost_usd": t["sum_cost_usd"], "provider_usage": provider_usage(rows4)[a]}
               for a, t in json.loads((X / "k4" / "analysis-k4.json").read_text())["per_arm"].items()}}}))
del probe_runner
print(OUT)
print(subprocess.run(["find", str(OUT), "-type", "f"], capture_output=True, text=True).stdout.count("\n"), "files")
