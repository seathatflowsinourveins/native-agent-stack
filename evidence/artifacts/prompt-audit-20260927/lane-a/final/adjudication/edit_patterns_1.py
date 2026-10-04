"""One-off edit of void_patterns_final.py, audit_final.py and audit_selftest_final.py before dispatch: JSON-escaped
family-verdict forms, the two exempt attachment kinds, the probe path and the MAPPING hits on a2-gpt6 paths."""
from pathlib import Path

X = Path(__file__).resolve().parent


def sub(name, pairs):
    p = X / name
    t = p.read_text()
    for a, b in pairs:
        assert t.count(a) == 1, (name, a[:70])
        t = t.replace(a, b)
    p.write_text(t)


sub("void_patterns_final.py", [
    ('''    r"gpt6\\.runner\\.json", r"x5-adj-(?:AB|BA)", r"\\"gpt6\\":\\s*\\"(?:agree|amend|reject)\\"",
    r"\\"claude\\":\\s*\\"(?:agree|amend|reject)\\"",''',
     '''    r"gpt6\\.runner\\.json", r"x5-adj-(?:AB|BA)",'''),
    ('''    r"\\"(?:gpt6|claude)\\"\\s*:\\s*\\[\\s*\\"(?:agree|amend|reject)\\"",
    r"\\"(?:gpt6|claude)\\"\\s*:\\s*\\{\\s*\\"verdict\\"\\s*:\\s*\\"(?:agree|amend|reject)\\""]), re.I)''',
     '''    # a family key with a verdict value, as a string, a list or a verdict object; quotes may be JSON-escaped
    r'\\\\?"(?:gpt6|claude)\\\\?"\\s*:\\s*(?:\\[\\s*|\\{\\s*\\\\?"verdict\\\\?"\\s*:\\s*)?\\\\?"(?:agree|amend|reject)\\\\?"']),
    re.I)'''),
    ('''  It applies only to context a Claude judge did not fetch (attachments, including hook context, and advisor
  results), because the repository's own prose about the two families is subject matter in files a judge reads.
  The prompts are frozen before dispatch and scanned by root_scan_final.py instead.''',
     '''  It applies only to context a Claude judge did not fetch (attachments, including hook context, and advisor
  results), because the repository's own prose about the two families is subject matter in files a judge reads.
  The prompts are frozen before dispatch and scanned by root_scan_final.py instead. Two attachment kinds are
  exempt: prompt_snapshot is the judge's own agent definition, whose leak rule quotes "Claude's proposal" as an
  example; session_context is the client's start-of-session snapshot (the user's email and the live checkout's git
  status), whose commit subjects name lanes as subject matter, so its hits are reported, not voiding, and no commit
  is made while judges run.'''),
])
sub("audit_final.py", [
    ('''            a.check(body, f"attachment {kind}", ["MAPPING", "INJECTED"], quiet=quiet)''',
     '''            a.check(body, f"attachment {kind}", ["MAPPING"], quiet=quiet)
            if kind != "prompt_snapshot":  # the judge's own agent definition (void_patterns_final.py)
                a.check(body, f"attachment {kind}", ["INJECTED"], quiet=quiet, voiding=kind != "session_context")'''),
    ("- INJECTED: every attachment of a Claude judge, including hook context, and its advisor results;\n",
     "- INJECTED: every attachment of a Claude judge, including hook context, and its advisor results (the two exempt\n"
     "  attachment kinds are named in void_patterns_final.py);\n"),
])
sub("audit_selftest_final.py", [
    ('HOLD / "k2/work/gpt6/a2-gpt6-probe"', 'HOLD / "k2/work/gpt6/a2-probe"'),
    ('''    ("gpt6", f"/bin/bash -lc 'cat {SP}/k2/work/gpt6/a2-gpt6/events.jsonl'",
     {"ACCESS:hold_and_work_dirs", "ACCESS:other_lane"}),
    ("gpt6", f"/bin/bash -lc 'cat {SP}/.hold3/k2/work/gpt6/a2-gpt6/result.json'",
     {"ACCESS:hold_and_work_dirs", "ACCESS:other_lane"}),''',
     '''    ("gpt6", f"/bin/bash -lc 'cat {SP}/k2/work/gpt6/a2-gpt6/events.jsonl'",
     {"ACCESS:hold_and_work_dirs", "ACCESS:other_lane", "MAPPING"}),
    ("gpt6", f"/bin/bash -lc 'ls {SP}/.hold3/k2/work/gpt6'", {"ACCESS:hold_and_work_dirs", "ACCESS:other_lane"}),'''),
    ('''    ("claude", read(f"{SP}/.hold3/k2/work/gpt6/a2-gpt6/result.json"),
     {"ACCESS:hold_and_work_dirs", "ACCESS:other_lane"}),''',
     '''    ("claude", read(f"{SP}/.hold3/k2/work/gpt6/a2-gpt6/result.json"),
     {"ACCESS:hold_and_work_dirs", "ACCESS:other_lane", "MAPPING"}),
    ("claude", read(f"{SP}/.hold3/k2/work", tool="Glob"), {"ACCESS:hold_and_work_dirs", "ACCESS:other_lane"}),'''),
    ('''    ("claude", hook("<context_guidance><tip>Reading to Edit the file? Read is correct.</tip></context_guidance>"),
     set()),''',
     '''    ("claude", hook("<context_guidance><tip>Reading to Edit the file? Read is correct.</tip></context_guidance>"),
     set()),
    ("claude", hook('{"gpt6": {"verdict": "amend", "confidence": 0.6}}'), {"MAPPING", "INJECTED"}),
    ("claude", [{"type": "attachment", "attachment": {"type": "prompt_snapshot", "systemPrompt": [
        "a phrase that attributes a return to a reviewer family, such as \\"the Codex lane\\" or \\"Claude's proposal\\""]}}],
     set()),
    ("claude", [{"type": "attachment", "attachment": {"type": "session_context", "context": {"gitStatus":
        "4f31ef46 OmniRoute routing convergence: GPT-6 lane account-routing adjudication (51 items)"}}}], set()),
    ("claude", [{"type": "attachment", "attachment": {"type": "session_context", "context": {"gitStatus":
        '{"gpt6": ["agree", 0.94]}'}}}], {"MAPPING"}),'''),
])
print("ok")
