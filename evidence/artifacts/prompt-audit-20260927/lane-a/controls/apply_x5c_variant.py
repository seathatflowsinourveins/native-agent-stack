"""Set the X5 worktree's (wt-x5) Codex template line 3 to one X5c text, optionally with its test pins, to measure a
text before the final adjudication compares it and to apply the adjudicated outcome afterwards.

usage: apply_x5c_variant.py base|proposal|amendment [--pin]
- base: the text at main 8315274f (proposals.json X5c "old"); proposal: the packet's proposed text (proposals.json
  X5c "new"); amendment: the final round's amending lane's resolution_text (returns/claude.json X5c).
- The current line 3 must be one of the three; each change is an exact match.
- --pin also sets tests/test_codex_worker_lane.py's TOP_RULE_SHA256 (:47), the word count at :210 and the :45 comment
  to the values the test module's own template_segments() computes from the template as written; without --pin the
  test is left as it is (the failing control).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

A2 = Path(__file__).resolve().parent.parent
W3 = A2.parent
WT = W3.parent / "wt-x5"
TEMPLATE = "adoption/templates/codex.AGENTS.template.md"
item = next(i for i in json.loads((W3 / "proposals.json").read_text())["items"] if i["id"] == "X5c")
assert item["file"] == TEMPLATE
amend = next(i for i in json.loads((A2 / "returns" / "claude.json").read_text())["items"] if i["id"] == "X5c")
assert amend["verdict"] == "amend" and amend["resolution_text"].strip()
TEXTS = {"base": item["old"], "proposal": item["new"], "amendment": amend["resolution_text"].strip()}
want = sys.argv[1]
pin = sys.argv[2:] == ["--pin"]
assert want in TEXTS and sys.argv[2:] in ([], ["--pin"]), __doc__

tpl = WT / TEMPLATE
lines = tpl.read_text(encoding="utf-8").split("\n")
current = [k for k, t in TEXTS.items() if lines[2] == t]
assert len(current) == 1, f"line 3 is none of {list(TEXTS)}: {lines[2]!r}"
lines[2] = TEXTS[want]
tpl.write_text("\n".join(lines), encoding="utf-8")
print("line 3:", current[0], "->", want)
if pin:
    probe = ("import hashlib\nfrom tests import test_codex_worker_lane as t\ntop, _, _ = t.template_segments()\n"
             "print(hashlib.sha256(top.encode('utf-8')).hexdigest(), len(top.split()))\n")
    new_sha, words = subprocess.run([sys.executable, "-B", "-c", probe], cwd=WT, capture_output=True, text=True,
                                    check=True).stdout.split()
    test = WT / "tests" / "test_codex_worker_lane.py"
    t = test.read_text(encoding="utf-8")
    subs = [(r'TOP_RULE_SHA256 = "[0-9a-f]{64}"', f'TOP_RULE_SHA256 = "{new_sha}"'),
            (r"self\.assertEqual\(len\(top\.split\(\)\), \d+\)", f"self.assertEqual(len(top.split()), {words})"),
            (r"# The staged top-rule block \(\d+ words by `wc -w`",
             f"# The staged top-rule block ({words} words by `wc -w`")]
    for rx, new in subs:
        t, n = re.subn(rx, lambda _m: new, t)
        assert n == 1, f"not found once: {rx}"
    test.write_text(t, encoding="utf-8")
    print(json.dumps({"top_rule_sha256": new_sha, "words": int(words)}))
