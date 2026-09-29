"""Copy X9's third round (the K5-K6 comparison and the four blind judgments) into the PR #444 worktree as evidence.

usage: package_x9_round3.py
Target: <hold>/wt-pa-r3/evidence/artifacts/prompt-audit-20260927/x9-round3/. Round 2's package_x9_attempt2.py with
round 3's files:
- the preregistration, harness, grader, fixtures and judge scripts byte for byte; every file prereg-r3.json hashes is
  checked here against its published copy (the three arm files are round 2's published arms, checked the same way,
  and the four raw probe transcripts are not published). The two files changed after freezing are published twice:
  as frozen (*.frozen.py, with the preregistered hash) and as run;
- promptfooconfig-r3.yaml, isolate_r3.sh, the isolation output and the judges' prompts with host paths replaced
  (judges/sent-sha256.json keeps the hashes of the files as the judges received them);
- the comparison's results in compact form: per run the facts the metrics read, the init event reduced to the fixture
  server's status and whether the fixture plugin loaded, and no session ids. Answer heads and status sentences are
  withheld by make_x9_round3.py's own rule (its code, taken with ast), the rule the judges' packets used;
- probes p1-p4 as probe_facts.py's fixture-only facts, the answer withheld by the same rule;
- the four judgments with their audit, tally, actions and usage.
Refuses to write a file that still holds a host path, a home directory, a UUID or an e-mail address. The host user
name is written as <user> (added 2026-09-28, as lane A's package_lane_a.py does: exposure_scan_dir.py's home
pattern held it as a literal) and refused anywhere it remains.
"""
import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

W3 = Path(__file__).resolve().parent
HOLD = W3.parent
S = HOLD.parent
X3 = W3 / "x9-round3"
J3 = HOLD / "j3" / "x9"  # moved into the hold directory after the judges finished
WT = HOLD / "wt-pa-r3"
OUT = WT / "evidence" / "artifacts" / "prompt-audit-20260927" / "x9-round3"
ROUND2 = OUT.parent / "x9-round2"
SUBS = sorted([(str(S / "j3" / "x9" / "root"), "<root>"), (str(S / "j3" / "x9"), "<judges>"),
               (str(J3 / "root"), "<root>"), (str(J3), "<judges>"),
               (str(S / "convergence-r3" / "x9-round3"), "<x9-round3>"), (str(X3), "<x9-round3>"),
               (str(S / "convergence-r3"), "<work>"), (str(W3), "<work>"),
               (str(S / "wt-x9r3-g"), "<worktree g>"), (str(S / "wt-x9r3-c"), "<worktree c>"),
               (str(S / "wt-x9r3-0"), "<worktree 0>"), (str(HOLD), "<hold>"), (str(S), "<scratch>"),
               (str(S.parent), "<session>"), (str(Path.home() / ".claude" / "projects"), "<projects>"),
               (f"{S.parent.parent.name}/{S.parent.name}", "<project-dir>/<session-id>")],
              key=lambda p: -len(p[0]))
PRIVATE = re.compile(r"/tmp/claude-\d+|-home-[A-Za-z0-9_]+-|/(?:home|Users)/[A-Za-z0-9_.-]+"
                     r"|[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}", re.I)
RUNNER_KEYS = ("status", "exit", "started", "finished", "usage", "usage_status", "limit", "limit_marker", "model",
               "effort", "codex_version", "attempts")
written = []


def clean(text):
    for old, new in SUBS:
        text = text.replace(old, new)
    return re.sub(r"/home/[A-Za-z0-9_.-]+", "~", text).replace(Path.home().name, "<user>")


def write(name, text, verbatim=False):
    if not verbatim:
        text = clean(text)
    # Not addresses: the commit trailer's no-reply address, and the fixture's @mcp.tool decorator after an escaped
    # newline in a JSON string ("\\n@mcp.tool").
    hits = [m.group(0) for m in PRIVATE.finditer(text)
            if m.group(0) != "noreply@anthropic.com" and not m.group(0).endswith("@mcp.tool")]
    if hits:
        sys.exit(f"{name}: private content left: {sorted(set(h[:24] for h in hits))[:5]}")
    if Path.home().name in text:
        sys.exit(f"{name}: the host user name is left")
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if verbatim:
        path.write_bytes(text.encode())
    else:
        path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    written.append(name)


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1)


# make_x9_round3.py's withholding rule and host-path substitutions, taken from the builder that made the packets.
tree = ast.parse((W3 / "make_x9_round3.py").read_text())
mk = {"re": re, "sys": sys, "json": json, "X3": X3}
for node in tree.body:
    names = {getattr(t, "id", "") for t in node.targets} if isinstance(node, ast.Assign) else set()
    if names & {"HELD_HEAD", "HELD_SENT", "HOST", "SETTINGS", "CONSULTED", "CONFIG"} or (
            isinstance(node, ast.FunctionDef) and node.name in ("consulted", "clean")):
        exec(compile(ast.Module([node], []), "make_x9_round3.py", "exec"), mk)
HELD_HEAD, HELD_SENT, CONFIG, SETTINGS = mk["HELD_HEAD"], mk["HELD_SENT"], mk["CONFIG"], mk["SETTINGS"]


def withheld_head(evidence_settings, head):
    return bool(evidence_settings) or bool(CONFIG.search(head or "")) or bool(SETTINGS.search(head or ""))


def withheld_sentence(sentence):
    return bool(CONFIG.search(sentence or "")) or bool(SETTINGS.search(sentence or ""))


OUT.mkdir(parents=True, exist_ok=True)
prereg = json.loads((X3 / "prereg-r3.json").read_text())
assert hashlib.sha256((X3 / "prereg-r3.json").read_bytes()).hexdigest() == \
    (X3 / "prereg-r3.sha256").read_text().split()[0]

# 1. Byte for byte, with every preregistered hash checked against the published copy.
VERBATIM = ["prereg-r3.json", "prereg-r3.sha256", "prereg-r3.draft.json", "freeze_prereg_r3.py", "run_arm_r3.sh",
            "probe_r3.sh", "summarize.py", "summarize_r3.py", "metrics.py", "metrics_r3.py", "analyze_r3.py",
            "grader_selftest.py", "probe_facts.py", "void_patterns_r3.py", "audit_r3.py", "tally_r3.py",
            "check_orders_r3.py", "check_orders_r3.frozen.py", "make_x9_round3.frozen.py"]
VERBATIM += [f"fixtures/{rel}" for rel in prereg["fixture_files"]]
for name in VERBATIM:
    write(name, (X3 / name).read_text(), verbatim=True)
write("make_x9_round3.py", (W3 / "make_x9_round3.py").read_text(), verbatim=True)
published = {"../make_x9_round3.py": "make_x9_round3.frozen.py", "check_orders_r3.py": "check_orders_r3.frozen.py"}
REPLACED = {"promptfooconfig-r3.yaml"}
arms = {}
for key, want in prereg["sha256"].items():
    if key.startswith("<worktree "):
        arm = key.split()[1][0]  # "<worktree g>/CLAUDE.md"
        path = ROUND2 / "arms" / f"CLAUDE.{arm}.md"
        arms[arm] = {"published": f"../x9-round2/arms/CLAUDE.{arm}.md", "sha256": want}
    elif key.startswith("probe/") and key.endswith(".jsonl"):
        continue  # raw transcripts: not published
    elif key in REPLACED:
        path = X3 / key  # published with host paths replaced; the hash is of the file as run
    else:
        path = OUT / published.get(key, key)
    got = hashlib.sha256(path.read_bytes()).hexdigest()
    if got != want:
        sys.exit(f"preregistered hash mismatch for {key}: {path.name} {got[:8]} != {want[:8]}")
changed = {k: {"frozen": hashlib.sha256((OUT / v).read_bytes()).hexdigest(),
               "as_run": hashlib.sha256((OUT / Path(k).name).read_bytes()).hexdigest()}
           for k, v in published.items()}
write("prereg-check.json", dump({
    "note": "Each file prereg-r3.json hashes, checked against its published copy when this directory was written. "
            "The arm files are round 2's published arms (identical bytes). promptfooconfig-r3.yaml names the harness "
            "directory by its host path, so its hash was checked on the file as run and the published copy has that "
            "path replaced. The four raw probe transcripts are not "
            "published (they hold the host's init data). Two files changed after freezing and are published twice: "
            "the frozen copy carries the preregistered hash, the as-run copy is what ran.",
    "checked": sorted(k for k in prereg["sha256"] if not (k.startswith("probe/") and k.endswith(".jsonl"))),
    "not_published": sorted(k for k in prereg["sha256"] if k.startswith("probe/") and k.endswith(".jsonl")),
    "published_with_host_paths_replaced": sorted(REPLACED),
    "arms": arms, "changed_after_freezing": changed}))

# 2. Host paths replaced.
write("promptfooconfig-r3.yaml", (X3 / "promptfooconfig-r3.yaml").read_text())
write("eval-r3.log", (X3 / "eval-r3.log").read_text())
write("isolate_r3.sh", (X3 / "isolate_r3.sh").read_text())
write("isolation-receipt.json", (X3 / "isolation-receipt-r3.json").read_text())
write("isolation_receipt_r3.py", (X3 / "isolation_receipt_r3.py").read_text())
write("run-window.json", dump({"started": (X3 / "run.started").read_text().strip(),
                               "finished": (X3 / "run.finished").read_text().strip()}))

# 3. The comparison: analysis and compact results, withheld by the packets' rule.
analysis = json.loads((X3 / "analysis-r3.json").read_text())
held = {"answer heads": 0, "status sentences": 0}
head_held = {}
for r in analysis["runs"]:
    if withheld_sentence(r.get("status_sentence")):
        r["status_sentence"], held["status sentences"] = HELD_SENT, held["status sentences"] + 1
    elif r.get("status_sentence"):
        r["status_sentence"] = mk["clean"](r["status_sentence"])
    head_held[r["transcript"]] = withheld_head(r["evidence_settings"], r["final_head"])
    if head_held[r["transcript"]]:
        r["final_head"], held["answer heads"] = HELD_HEAD, held["answer heads"] + 1
    else:
        r["final_head"] = mk["clean"](r["final_head"])
    r["consulted"] = mk["consulted"](r)
assert held == {"answer heads": 17, "status sentences": 0}, held
analysis["withheld"] = {"rule": "make_x9_round3.py: an answer head is withheld when its run read client settings "
                                "files or it matches the configuration or settings-file patterns; a status sentence "
                                "when it matches them", "counts": held}
write("analysis-r3.json", dump(analysis))


def reduced_init(init):
    names = [p if isinstance(p, str) else p.get("name") for p in init.get("plugins") or []]
    servers = init.get("mcp_servers") or {}
    status = servers.get("ticket-tracker") if isinstance(servers, dict) else next(
        (s.get("status") for s in servers if s.get("name") == "ticket-tracker"), None)
    return {"version": init.get("version"), "model": init.get("model"), "permission_mode": init.get("permission_mode"),
            "ticket_tracker_status": status, "workspace_guard_loaded": "workspace-guard" in names}


def facts(output):
    s = json.loads(output)
    held_head = head_held[s["transcript"]]
    return {**{k: s.get(k) for k in ("arm", "transcript", "exit", "duration_ms", "result_subtype", "num_turns",
                                     "cost_usd", "usage", "target_tools_in_init", "hook", "mcp")},
            "init": reduced_init(s.get("init") or {}),
            "calls": [{k: c.get(k) for k in ("name", "skill", "query", "is_error")} for c in s.get("calls") or []],
            "final_head": HELD_HEAD if held_head else mk["clean"]((s.get("final") or "")[:400])}


res = json.loads((X3 / "results-r3.json").read_text())
rows = [{"provider": r["provider"].get("label"), "vars": {k: r["vars"][k] for k in ("case", "target") if k in r["vars"]},
         "latency_ms": r.get("latencyMs"),
         "assertions": {c["assertion"]["metric"]: c["pass"] for c in r["gradingResult"]["componentResults"]},
         "output": facts(r["response"]["output"])} for r in res["results"]["results"]]
write("results-r3-compact.json", dump({"harness": res["metadata"], "eval_id": res["evalId"],
                                       "runtime_options": res.get("runtimeOptions"), "stats": res["results"]["stats"],
                                       "rows": rows}))

# 4. Probes: probe_facts.py's fixture-only facts; the answer withheld by the same rule (a probe's reads are not
# graded, so the head rule's settings flag is taken from its commands, as consulted() reads them).
probes = {}
for name in ("p1-ok", "p2-k6-view", "p3-k5-view", "p4-k6-refused"):
    out = subprocess.run([sys.executable, str(X3 / "probe_facts.py"), name, "--answer"], capture_output=True,
                         text=True, check=True).stdout
    body, _, answer = out.partition("\nANSWER: ")
    f = json.loads(body)
    reads = mk["consulted"]({"arm": "../probe", "transcript": f"{name}.jsonl"})
    f["answer"] = HELD_HEAD if withheld_head("settings files" in reads, answer) else mk["clean"](answer.strip())
    f["consulted"] = reads
    probes[name] = f
write("probe/facts.json", dump({"note": "Uncounted probes p1-p4 (prereg-r3.json, uncounted_probes): probe_facts.py's "
                                        "fixture-only facts, the answer withheld by the packets' rule; the raw "
                                        "transcripts are not published.", "probes": probes}))
for name in ("p1-ok", "p2-k6-view", "p3-k5-view", "p4-k6-refused"):
    write(f"probe/{name}.mcplog", (X3 / "probe" / f"{name}.mcplog").read_text())

# 5. The judges: what they received (host paths replaced; hashes of the originals kept), returns, audit, tally.
sent = {}
for d in ("adjudication-inputs", "packets", "prompts", "schemas"):
    for f in sorted((J3 / d).iterdir()):
        sent[f"{d}/{f.name}"] = hashlib.sha256(f.read_bytes()).hexdigest()
        write(f"judges/{d}/{f.name}", f.read_text())
write("judges/sent-sha256.json", dump({
    "note": "sha256 of each file as the judges received it. The published copies replace the host path of the judges' "
            "directory and repository root with <judges> and <root>; the packets and prompts were built with the "
            "answer heads of runs that read client settings files already withheld (make_x9_round3.py).",
    "files": sent}))
write("judges/mapping.json", (X3 / "round3-mapping.json").read_text())
for order in ("AB", "BA"):
    r = json.loads((X3 / "returns" / f"gpt6-{order}.runner.json").read_text())
    write(f"judges/gpt6.{order}.json", dump({"lane": "GPT-6 packaged runner (codex_call.sh start/result)",
                                             "runner": {k: r[k] for k in RUNNER_KEYS if k in r},
                                             "return": json.loads(r["output_text"])}))
usage = json.loads((X3 / "claude-usage-r3.json").read_text())
for order in ("AB", "BA"):
    write(f"judges/claude.{order}.json", dump({
        "lane": "Claude Agent tool, blind-adjudicator (frontmatter model opus, effort max; Read, Glob and Grep only)",
        "usage": usage[f"judge-{order}"], "return": json.loads((X3 / "returns" / f"claude-{order}.json").read_text())}))
write("judges/audit.json", (X3 / "audit-r3.json").read_text())
write("judges/tally.json", (X3 / "tally-r3.json").read_text())
write("judges/judge-actions.json", (X3 / "judge-actions-r3.json").read_text())
for name in ("judge_actions_r3.py", "claude_usage_r3.py"):
    write(f"judges/{name}", (X3 / name).read_text())
write("sources-r3.json", (W3 / "sources-r3.json").read_text())


def runner(p):
    return {k: v for k, v in json.loads(p.read_text()).items() if k in ("status", "exit", "limit", "usage")}


per_arm = analysis["per_arm"]
write("usage.json", dump({
    "note": "Provider usage of X9's third round. Anthropic usage fields are disjoint and listed side by side, never "
            "added; each Codex runner record is its own. The comparison's cost is the client's per-run "
            "total_cost_usd estimate; the probes are uncounted runs. The coordinator session is not included.",
    "comparison_runs": {a: {"runs": t.get("n"), "sum_cost_usd": t.get("sum_cost_usd"),
                            "provider_usage": {k: sum((row["output"].get("usage") or {}).get(k) or 0 for row in rows
                                                      if row["provider"] == f"arm-{a}")
                                               for k in ("input_tokens", "cache_creation_input_tokens",
                                                         "cache_read_input_tokens", "output_tokens")}}
                        for a, t in per_arm.items()},
    "probes": {n: {"cost_usd": json.loads((X3 / "probe" / f"{n}.summary.json").read_text()).get("cost_usd"),
                   "usage": json.loads((X3 / "probe" / f"{n}.summary.json").read_text()).get("usage")}
               for n in ("p1-ok", "p2-k6-view", "p3-k5-view", "p4-k6-refused")},
    "claude_judges": usage,
    "source_research": {**json.loads((X3 / "claude-usage-research-r3.json").read_text()),
                        "served": "X9 (Q1, Q2: the fixtures) and lane A (Q3-Q5); counted here only"},
    "gpt6_judges": {f"judge-{o}": runner(X3 / "returns" / f"gpt6-{o}.runner.json") for o in ("AB", "BA")}}))
write("exposure_scan_dir.py", (W3 / "exposure_scan_dir.py").read_text())
write("package_x9_round3.py", Path(__file__).read_text())
print(OUT)
print(len(written), "files;", "withheld", held)
