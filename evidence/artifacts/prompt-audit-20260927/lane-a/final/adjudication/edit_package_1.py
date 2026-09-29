"""One-off edit of package_lane_a.py for the final X5c adjudication: the lanes' directory moved under the hold
directory, the adjudication's own directory (j7/x5c), an explicit file list for the adjudication instead of copying
its whole work directory, and the amendment's measured checks in controls.json."""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "package_lane_a.py"
t = p.read_text()
pairs = [
    ('''J6, K2 = HOLD / "j6" / "x5", S / "k2"''',
     '''J6, K2, K2_SENT = HOLD / "j6" / "x5", HOLD / "k2", S / "k2"  # the lanes read k2 at K2_SENT; moved before the
J7, AD = S / "j7" / "x5c", A2 / "adjudication"                     # final adjudication (j7/x5c) was dispatched'''),
    ('''SUBS = sorted([(str(K2 / "root"), "<root>"), (str(K2), "<k2>"),''',
     '''SUBS = sorted([(str(K2 / "root"), "<root>"), (str(K2), "<k2>"), (str(K2_SENT / "root"), "<root>"),
               (str(K2_SENT), "<k2>"), (str(J7 / "root"), "<root>"), (str(J7), "<judges>"),'''),
    ('''        ("the complete proposal: every test module that reads either template or the pin",
         f"python3 -B -m unittest {TARGETED}", A2 / "x5-proposal-targeted-tests.log", r"^(Ran |OK|FAILED)", 0)):''',
     '''        ("the complete proposal: every test module that reads either template or the pin",
         f"python3 -B -m unittest {TARGETED}", A2 / "x5-proposal-targeted-tests.log", r"^(Ran |OK|FAILED)", 0),
        ("X5c amendment: its line 3, test at the proposal's pin (no re-pin)", f"python3 -B -m unittest {PIN}",
         AD / "x5c-amend-control-template-only.log", SUMMARY, 1),
        ("X5c amendment: its line 3 with the re-pinned test", f"python3 -B -m unittest {PIN}",
         AD / "x5c-amend-repinned.log", SUMMARY, 0),
        ("registration: amendment's template and test edited, not re-registered", "python3 scripts/validate.py",
         AD / "x5c-amend-validate-before-registration.log", r"\\S", 1),
        ("registration: amendment's template and test registered", "python3 scripts/validate.py",
         AD / "x5c-amend-validate-after-registration.log", r"\\S", 0),
        ("the complete amendment: every test module that reads either template or the pin",
         f"python3 -B -m unittest {TARGETED}", AD / "x5c-amend-targeted-tests.log", r"^(Ran |OK|FAILED)", 0)):'''),
    ('''for f in ("apply_x5c_trial.py", "register_files.py"):
    copy(W3 / f, f"controls/{f}")
copy(A2 / "apply_x5a_trial.py", "controls/apply_x5a_trial.py")''',
     '''for f in ("apply_x5c_trial.py", "register_files.py"):
    copy(W3 / f, f"controls/{f}")
copy(A2 / "apply_x5a_trial.py", "controls/apply_x5a_trial.py")
copy(AD / "apply_x5c_variant.py", "controls/apply_x5c_variant.py")'''),
    ('''adj = A2 / "adjudication"
if adj.exists():
    for p in sorted(adj.rglob("*")):
        if p.is_file() and "runs" not in p.parts and p.suffix in (".json", ".txt", ".py", ".md", ".sha256"):
            copy(p, f"final/adjudication/{p.relative_to(adj)}")''',
     '''# Final adjudication of X5c: sent files (host paths replaced; hashes as sent), the root's amendment diff, the
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
    "note": "sha256 of each file as the judges received it; the published inputs, packet and prompts replace host "
            "paths with <judges> and <root>. root/proposal.diff and root/packet.md are byte for byte the final "
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
          "edit_patterns_2.py", "edit_patterns_3.py", "edit_package_1.py"):
    copy(AD / f, f"{FA}/{f}")'''),
]
for a, b in pairs:
    assert t.count(a) == 1, a[:80]
    t = t.replace(a, b)
t = t.replace('"""Copy lane A (S1 and X5a-c: round 1, its two adjudication attempts, the trial controls and the final round) into a\nworktree as evidence.',
              '"""Copy lane A (S1 and X5a-c: round 1, its two adjudication attempts, the trial controls, the final round and its\nX5c adjudication) into a worktree as evidence.')
p.write_text(t)
print("ok")
