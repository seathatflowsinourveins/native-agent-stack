"""Copy lane A (S1 and X5a-c: round 1, its two adjudication attempts, the trial controls, the final round and its
X5c adjudication) into a worktree as evidence.

usage: package_lane_a.py WORKTREE
Target: WORKTREE/evidence/artifacts/prompt-audit-20260927/lane-a/. package_x9_round3.py's rules:
- scripts, schemas, the frozen packets and the diff byte for byte where they hold no host path;
- prompts, inputs, returns, audits and judge actions with host paths replaced (each directory's sent-sha256.json
  keeps the hashes of the files as their judges received them);
- runner records reduced to the runner's own status, timing, usage and model fields;
- the trial controls as commands, exit codes and the output lines the packet quoted, never whole logs.
Not published: the judges' and lanes' session transcripts and Codex event logs (they carry the host's injected
context and home paths), and attempt 1's two GPT-6 returns, which were never read (attempt1/void.json).
Refuses to write a file that still holds a host path, a home directory, a UUID or an e-mail address.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

A2 = Path(__file__).resolve().parent
W3 = A2.parent
HOLD = W3.parent
S = HOLD.parent
L, ADJ = W3 / "lane-a", W3 / "lane-a" / "adj"
J6, K2, K2_SENT = HOLD / "j6" / "x5", HOLD / "k2", S / "k2"  # the lanes read k2 at K2_SENT; moved before the
J7, AD = S / "j7" / "x5c", A2 / "adjudication"                     # final adjudication (j7/x5c) was dispatched
OUT = Path(sys.argv[1]).resolve() / "evidence" / "artifacts" / "prompt-audit-20260927" / "lane-a"
SUBS = sorted([(str(K2 / "root"), "<root>"), (str(K2), "<k2>"), (str(K2_SENT / "root"), "<root>"),
               (str(K2_SENT), "<k2>"), (str(J7 / "root"), "<root>"), (str(J7), "<judges>"),
               (str(J6 / "root"), "<root>"), (str(S / "j6" / "x5" / "root"), "<root>"),
               (str(J6), "<judges>"), (str(S / "j6" / "x5"), "<judges>"),
               (str(A2), "<lane-a2>"), (str(L), "<lane-a>"), (str(S / "convergence-r3" / "lane-a"), "<lane-a>"),
               (str(W3), "<work>"), (str(S / "convergence-r3"), "<work>"),
               (str(HOLD / "wt-x5"), "<worktree>"), (str(S / "wt-r3-base"), "<base>"),
               (str(HOLD / "wt-r3-base"), "<base>"), (str(HOLD), "<hold>"), (str(S), "<scratch>"),
               (str(S.parent), "<session>"), (str(Path.home() / ".claude" / "projects"), "<projects>"),
               ("<tmp>", "<tmp>"), (str(S.parent.parent), "<session-root>"),
               (S.parent.name, "<session-id>"), (S.parent.parent.name, "<project-dir>"),
               (str(S.parent.parent.parent), "<tmp-root>")], key=lambda p: -len(p[0]))
PRIVATE = re.compile(r"/tmp/claude-\d+|-home-[A-Za-z0-9_]+-|/(?:home|Users)/[A-Za-z0-9_.-]+"
                     r"|[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}", re.I)
AGENT_ID = re.compile(r"\ba[0-9a-f]{16}\b")  # a Claude subagent id, as in agent-<id>.jsonl
AGENT_IDS = {}
RUNNER_KEYS = ("status", "exit", "started", "finished", "usage", "usage_status", "limit", "limit_marker", "model",
               "effort", "codex_version", "attempts")
written = []


def clean(text):
    for old, new in SUBS:
        text = text.replace(old, new)
    text = re.sub(r"/home/[A-Za-z0-9_.-]+", "~", text)
    text = re.sub(r"-home-[A-Za-z0-9_]+-[A-Za-z0-9_-]*", "<project-dir>", text)
    text = re.sub(r"\b" + re.escape(S.parent.name[:8]) + r"[0-9a-f-]*", "<session-id>", text)
    text = text.replace(Path.home().name, "<user>")
    text = re.sub(r"plugins/cache/[\w.@+-]+/[\w.@+-]+/\d[\w.@+-]*/skills/[\w.@+-]+",
                  "plugins/cache/<marketplace>/<plugin>/<version>/skills/<skill>", text)
    for old, new in (("<marketplace>", "<marketplace>"), ("<plugin>/<version>", "<plugin>/<version>"),
                     ("<skill>", "<skill>")):
        text = text.replace(old, new)
    text = re.sub(r"(\.agents/skills/|\.codex/skills/)[\w.-]+", r"\1<skill>", text)
    text = re.sub(r"/tmp/claude-\d+", "<tmp-root>", text)
    text = AGENT_ID.sub(lambda m: AGENT_IDS.setdefault(m.group(0), f"<agent-id-{len(AGENT_IDS) + 1}>"), text)
    return re.sub(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", "<uuid>", text, flags=re.I)


def write(name, text, verbatim=False):
    if not verbatim:
        text = clean(text)
    hits = [m.group(0) for m in PRIVATE.finditer(text) if m.group(0) != "noreply@anthropic.com"]
    hits += AGENT_ID.findall(text)
    if hits:
        sys.exit(f"{name}: private content left: {sorted(set(h[:24] for h in hits))[:5]}")
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    written.append(name)


def copy(src, name, verbatim=False):
    write(name, Path(src).read_text(encoding="utf-8"), verbatim=verbatim)


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1)


def runner(path):
    r = json.loads(Path(path).read_text())
    return {k: r.get(k) for k in RUNNER_KEYS}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# Round 1: the lane packet, both lanes' prompts and returns, and the lane tally.
for f in ("packet.md", "packet.sha256", "schema.json", "tally-lanes.json", "gpt6.json", "claude.json",
          "gpt6-prompt.txt", "claude-brief.txt"):
    copy(L / f, f"round1/{f}", verbatim=f in ("packet.sha256", "schema.json", "tally-lanes.json"))
write("round1/gpt6.runner.json", dump(runner(L / "gpt6.runner.json")))
for f in ("proposals.json", "facts-s1.json", "user-level-top-rule.txt", "build_lane_a.py"):
    copy(W3 / f, f"round1/{f}")
copy(ADJ / "claude-usage-lane-a.json", "round1/claude-usage.json")

# Adjudication, attempt 1 (void before any GPT-6 result was read) and attempt 2.
copy(ADJ / "attempt1" / "void.json", "adjudication/attempt1/void.json")
copy(L / "make_adjudication_a.py", "adjudication/attempt1/make_adjudication_a.py")
copy(AD / "attempt1-gpt6-usage.json", "adjudication/attempt1/gpt6-usage.json")
copy(AD / "attempt1_usage.py", "adjudication/attempt1/attempt1_usage.py")
sent = {}
for sub in ("adjudication-inputs", "packets", "prompts", "schemas"):
    for f in sorted((J6 / sub).iterdir()):
        sent[f"{sub}/{f.name}"] = sha(f)
        copy(f, f"adjudication/attempt2/{sub}/{f.name}", verbatim=sub == "schemas")
write("adjudication/attempt2/sent-sha256.json", dump({
    "note": "sha256 of each file as the judges received it; the published prompts replace host paths with "
            "<judges> and <root>. The inputs, the packet and the schemas are byte for byte.", "files": sent}))
copy(L / "adjudication-mapping-a.json", "adjudication/attempt2/mapping.json", verbatim=True)
usage2 = json.loads((ADJ / "attempt2" / "claude-usage-adj2.json").read_text())
for order in ("AB", "BA"):
    write(f"adjudication/attempt2/gpt6.{order}.json", dump({
        "runner": runner(ADJ / "attempt2" / "returns" / f"gpt6-{order}.runner.json"),
        "return": json.loads((ADJ / "attempt2" / "returns" / f"gpt6-{order}.json").read_text())}))
    write(f"adjudication/attempt2/claude.{order}.json", dump({
        "usage": usage2.get(f"adj2-{order}"),
        "return": json.loads((ADJ / "attempt2" / "returns" / f"claude-{order}.json").read_text())}))
for src, name in (("audit-a.json", "audit.json"), ("tally-a.json", "tally.json"),
                  ("judge-actions-a.json", "judge-actions.json"), ("claude-usage-adj2.json", "claude-usage.json")):
    copy(ADJ / "attempt2" / src, f"adjudication/attempt2/{name}")
copy(L / "make_adjudication_a2.py", "adjudication/attempt2/make_adjudication_a2.py")
for f in ("void_patterns_a.py", "audit_a.py", "audit_selftest_a.py", "audit-selftest-a.json", "root_scan_a.py",
          "tally_a.py", "save_return_a.py", "judge_actions_a.py"):
    copy(ADJ / f, f"adjudication/attempt2/{f}")

# Trial controls: commands, exit codes and the lines the final packet quoted.
SUMMARY = r"^(Ran |OK|FAILED|FAIL:|ERROR:|AssertionError)"
TOP = "tests.test_install_claude_profile.PortableTopRuleTests"
PIN = "tests.test_codex_worker_lane.TemplateTests.test_top_rule_and_upstream_text_are_verbatim"
TARGETED = ("tests.test_install_claude_profile tests.test_codex_worker_lane tests.test_codex_agents "
            "tests.test_codex_lane tests.test_landscape_sweep_harness tests.test_adoption_docs_consistency")
controls = []
for stage, cmd, log, rx, code in (
        ("X5c: proposed line 3, test at the base (no re-pin)", f"python3 -B -m unittest {PIN}",
         W3 / "x5c-control-template-only.log", SUMMARY, 1),
        ("X5c: proposed line 3 with the re-pinned test", f"python3 -B -m unittest {PIN}",
         W3 / "x5c-control-repinned.log", SUMMARY, 0),
        ("X5c: the four X5c test modules on the trial", "python3 -m unittest tests.test_codex_worker_lane "
         "tests.test_codex_agents tests.test_codex_lane tests.test_landscape_sweep_harness",
         W3 / "x5c-trial-tests.log", r"^(Ran |OK|FAILED)", 0),
        ("registration: X5c files edited, manifest not re-registered", "python3 scripts/validate.py",
         W3 / "x5c-validate-before-registration.log", r"\S", 1),
        ("X5a: round-1 proposed text (capital 'Never')", f"python3 -B -m unittest {TOP}",
         A2 / "x5a-control-roundone-text.log", SUMMARY, 1),
        ("X5a: proposed text", f"python3 -B -m unittest {TOP}", A2 / "x5a-proposal-toprule.log", SUMMARY, 0),
        ("registration: X5c files registered, X5a template edited, not re-registered", "python3 scripts/validate.py",
         A2 / "x5a-validate-before-registration.log", r"\S", 1),
        ("registration: all three changed files registered", "python3 scripts/validate.py",
         A2 / "x5a-validate-after-registration.log", r"\S", 0),
        ("the complete proposal: every test module that reads either template or the pin",
         f"python3 -B -m unittest {TARGETED}", A2 / "x5-proposal-targeted-tests.log", r"^(Ran |OK|FAILED)", 0),
        ("X5c amendment: its line 3, test at the proposal's pin (no re-pin)", f"python3 -B -m unittest {PIN}",
         AD / "x5c-amend-control-template-only.log", SUMMARY, 1),
        ("X5c amendment: its line 3 with the re-pinned test", f"python3 -B -m unittest {PIN}",
         AD / "x5c-amend-repinned.log", SUMMARY, 0),
        ("registration: amendment's template and test edited, not re-registered", "python3 scripts/validate.py",
         AD / "x5c-amend-validate-before-registration.log", r"\S", 1),
        ("registration: amendment's template and test registered", "python3 scripts/validate.py",
         AD / "x5c-amend-validate-after-registration.log", r"\S", 0),
        ("the complete amendment: every test module that reads either template or the pin",
         f"python3 -B -m unittest {TARGETED}", AD / "x5c-amend-targeted-tests.log", r"^(Ran |OK|FAILED)", 0)):
    lines = [clean(x) for x in Path(log).read_text().splitlines() if re.search(rx, x)]
    controls.append({"stage": stage, "command": cmd, "exit": code, "output_lines": lines})
write("controls/controls.json", dump({
    "note": "Run by the coordinator on 2026-09-28 in one worktree of main 8315274f (<worktree>), in the order listed; "
            "test runs set TMPDIR to a private directory. Output lines are the ones each check printed that match "
            "its summary pattern, with host paths replaced.", "controls": controls}))
for f in ("apply_x5c_trial.py", "register_files.py"):
    copy(W3 / f, f"controls/{f}")
copy(A2 / "apply_x5a_trial.py", "controls/apply_x5a_trial.py")
copy(AD / "apply_x5c_variant.py", "controls/apply_x5c_variant.py")

# Final round: frozen inputs, both lanes, the audit and the tally (and any adjudication).
for sub, f in (("packets", "packet.md"), ("packets", "packet.sha256"), ("prompts", "gpt6-prompt.txt"),
               ("prompts", "claude-brief.txt"), ("prompts", "gpt6-probe.txt"), ("schemas", "lane.json")):
    copy(K2 / sub / f, f"final/{sub}/{f}", verbatim=f in ("packet.sha256", "lane.json"))
copy(K2 / "root" / "proposal.diff", "final/proposal.diff", verbatim=True)
write("final/sent-sha256.json", dump({
    "note": "sha256 of each file as the lanes received it; the published prompts replace host paths with <k2> and "
            "<root>. proposal.diff and the packet are byte for byte.",
    "files": {f"{sub}/{f}": sha(K2 / sub / f) for sub, f in (
        ("packets", "packet.md"), ("prompts", "gpt6-prompt.txt"), ("prompts", "claude-brief.txt"),
        ("schemas", "lane.json"))} | {"root/proposal.diff": sha(K2 / "root" / "proposal.diff")}}))
write("final/gpt6-probe.runner.json", dump(runner(A2 / "returns" / "gpt6-probe.runner.json")))
write("final/gpt6.json", dump({"runner": runner(A2 / "returns" / "gpt6.runner.json"),
                               "return": json.loads((A2 / "returns" / "gpt6.json").read_text())}))
write("final/claude.json", dump({"usage": json.loads((A2 / "claude-usage-final.json").read_text()),
                                 "return": json.loads((A2 / "returns" / "claude.json").read_text())}))
for f in ("frozen-a2.sha256", "dispatched-lanes.txt", "audit-lanes.json", "tally-final.json", "root-scan-a2.out",
          "audit-selftest-a2.json", "build_lane_a2.py", "void_patterns_a2.py", "audit_a2.py", "audit_selftest_a2.py",
          "root_scan_a2.py", "tally_final.py", "package_lane_a.py"):
    copy(A2 / f, f"final/{f}")
# Final adjudication of X5c: sent files (host paths replaced; hashes as sent), the root's amendment diff, the
# probe, the four judgments, the audit, the tally and every script and record fixed before dispatch.
FA = "final/adjudication"
sent = {}
for sub in ("adjudication-inputs", "packets", "prompts", "schemas"):
    for f in sorted((J7 / sub).iterdir()):
        sent[f"{sub}/{f.name}"] = sha(f)
        copy(f, f"{FA}/{sub}/{f.name}", verbatim=sub == "schemas")
for f in ("amendment.diff", "proposal.diff", "packet.md"):
    sent[f"root/{f}"] = sha(J7 / "root" / f)
copy(J7 / "root" / "amendment.diff", f"{FA}/amendment.diff", verbatim=True)
write(f"{FA}/sent-sha256.json", dump({
    "note": "sha256 of each file as the judges received it; the published prompts replace host paths with "
            "<judges> and <root>. The inputs, the packet and the schema are byte for byte; root/proposal.diff and root/packet.md are byte for byte the final "
            "round's (final/proposal.diff, final/packets/packet.md).", "files": sent}))
write(f"{FA}/probe.runner.json", dump(runner(AD / "probe" / "x5c-probe.runner.json")))
copy(AD / "probe" / "audit-probe.json", f"{FA}/probe-audit.json")
usage_adj = json.loads((AD / "claude-usage-adjudication.json").read_text())
for order in ("AB", "BA"):
    write(f"{FA}/gpt6.{order}.json", dump({
        "runner": runner(AD / "returns" / f"gpt6-{order}.runner.json"),
        "return": json.loads((AD / "returns" / f"gpt6-{order}.json").read_text())}))
    write(f"{FA}/claude.{order}.json", dump({
        "usage": usage_adj.get(f"adj-final-{order}"),
        "return": json.loads((AD / "returns" / f"claude-{order}.json").read_text())}))
for f in ("audit-final.json", "tally-adjudication-final.json", "adjudication-mapping-final.json",
          "claude-usage-adjudication.json", "audit-selftest-final.json", "root-scan-final.out", "withheld-check.json",
          "outcome-actions.md", "frozen-final.sha256", "dispatched-final.txt", "void_patterns_final.py",
          "audit_final.py", "audit_selftest_final.py", "root_scan_final.py", "build_root_final.py",
          "build_adjudication_final.py", "tally_adjudication_final.py", "withheld_summary.py", "edit_patterns_1.py",
          "edit_patterns_2.py", "edit_patterns_3.py", "edit_package_1.py", "edit_package_2.py", "edit_package_3.py", "edit_package_4.py", "edit_package_5.py", "edit_package_6.py", "edit_package_7.py", "antipattern-rows.md"):
    copy(AD / f, f"{FA}/{f}")
for f in ("token-counts-base.txt", "token-counts-after.txt"):
    copy(AD / f, f"{FA}/{f}")
copy(AD / "README.lane-a.md", "README.md")
for f in sorted((AD / "review").iterdir()):
    copy(f, f"review/{f.name}")
copy(AD / "verify_lane_a.py", "verify_lane_a.py")
copy(W3 / "exposure_scan_dir.py", "exposure_scan_dir.py")
print(len(written), "files written to", clean(str(OUT)))
