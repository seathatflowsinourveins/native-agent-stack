"""Apply X5c with every co-change it needs to the X5 worktree (wt-x5), each by exact match, to measure it before it
is proposed again: the template's line 3 (proposals.json), and the pin in tests/test_codex_worker_lane.py
(TOP_RULE_SHA256, the word count asserted at :210 and the :45 comment), recomputed from the new template with the
test module's own template_segments() rather than copied from a return.

usage: apply_x5c_trial.py
"""
import json
import subprocess
import sys
from pathlib import Path

W3 = Path(__file__).resolve().parent
WT = W3.parent / "wt-x5"
item = next(i for i in json.loads((W3 / "proposals.json").read_text())["items"] if i["id"] == "X5c")
tpl = WT / item["file"]
text = tpl.read_text(encoding="utf-8")
assert text.count(item["old"]) == 1, "template line 3 is not the proposal's old text"
tpl.write_text(text.replace(item["old"], item["new"]), encoding="utf-8")

probe = ("import hashlib\nfrom tests import test_codex_worker_lane as t\ntop, _, _ = t.template_segments()\n"
         "print(hashlib.sha256(top.encode('utf-8')).hexdigest(), len(top.split()), t.TOP_RULE_SHA256)\n")
new_sha, words, old_sha = subprocess.run([sys.executable, "-c", probe], cwd=WT, capture_output=True, text=True,
                                         check=True).stdout.split()
words = int(words)
test = WT / "tests" / "test_codex_worker_lane.py"
t = test.read_text(encoding="utf-8")
edits = [(f'TOP_RULE_SHA256 = "{old_sha}"', f'TOP_RULE_SHA256 = "{new_sha}"'),
         ("self.assertEqual(len(top.split()), 120)", f"self.assertEqual(len(top.split()), {words})"),
         ("# The staged top-rule block (120 words by `wc -w`, marker line included)",
          f"# The staged top-rule block ({words} words by `wc -w`, marker line included)")]
for old, new in edits:
    assert t.count(old) == 1, f"not found once: {old}"
    t = t.replace(old, new)
test.write_text(t, encoding="utf-8")
print(json.dumps({"top_rule_sha256": new_sha, "words": words, "previous_sha256": old_sha}))
