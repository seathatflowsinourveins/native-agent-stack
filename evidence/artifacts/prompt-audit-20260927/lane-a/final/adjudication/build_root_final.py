"""Build the read-only repository root for lane A's final X5c adjudication, while the X5 worktree (wt-x5) holds the
amendment, measured and registered (apply_x5c_variant.py amendment --pin; x5c-amend-*.log).

usage: build_root_final.py
<scratchpad>/j7/x5c/root/
  base/            k2/root/base: main at 8315274f (git archive, no history)
  proposed/        k2/root/proposed: the frozen packet's complete proposal (X5a and X5c with co-changes)
  amended/         base plus wt-x5's four changed files: X5a as proposed, and X5c as the amending return's text with
                   the co-changes it names (re-pin via template_segments(), 153 words, re-registration)
  proposal.diff    k2/root/proposal.diff
  amendment.diff   wt-x5's `git diff` of the same four files
Withheld from all three trees: the 2026-09-27 prompt-audit decision record and its evidence directory, which record
earlier review rounds by reviewer family (round 1's lane returns, reviews and adjudication).
"""
import filecmp
import json
import re
import shutil
import subprocess
from pathlib import Path

AD = Path(__file__).resolve().parent
A2 = AD.parent
W3 = A2.parent
HOLD = W3.parent
S = HOLD.parent
K2 = S / "k2"
WT = HOLD / "wt-x5"
J7 = S / "j7" / "x5c"
ROOT = J7 / "root"
CHANGED = ["adoption/templates/codex.AGENTS.template.md", "examples/claude-native/CLAUDE.md",
           "manifests/evidence.json", "tests/test_codex_worker_lane.py"]
WITHHELD = ["docs/decisions/2026-09-27-prompt-audit-resolution.md", "evidence/artifacts/prompt-audit-20260927"]

assert not J7.exists(), "j7/x5c already exists"
ROOT.mkdir(parents=True)
shutil.copytree(K2 / "root" / "base", ROOT / "base", symlinks=True)
shutil.copytree(K2 / "root" / "proposed", ROOT / "proposed", symlinks=True)
shutil.copyfile(K2 / "root" / "proposal.diff", ROOT / "proposal.diff")
shutil.copytree(ROOT / "base", ROOT / "amended", symlinks=True)
for f in CHANGED:
    shutil.copyfile(WT / f, ROOT / "amended" / f)
(ROOT / "amendment.diff").write_text(subprocess.run(["git", "-C", str(WT), "diff", "--", *CHANGED],
                                                    capture_output=True, text=True, check=True).stdout)


def differing(a, b, rel=""):
    c = filecmp.dircmp(a, b)
    out = [f"{rel}{n}" for n in c.diff_files + c.left_only + c.right_only]
    for n in c.subdirs:
        out += differing(Path(a) / n, Path(b) / n, f"{rel}{n}/")
    return out


for tree in ("proposed", "amended"):
    got = sorted(differing(ROOT / "base", ROOT / tree))
    assert got == sorted(CHANGED), (tree, got)
amend = next(i for i in json.loads((A2 / "returns" / "claude.json").read_text())["items"] if i["id"] == "X5c")
line3 = lambda tree, f: (ROOT / tree / f).read_text(encoding="utf-8").split("\n")[2]  # noqa: E731
assert line3("amended", CHANGED[0]) == amend["resolution_text"].strip()
assert line3("amended", CHANGED[1]) == line3("proposed", CHANGED[1]) != line3("base", CHANGED[1])
test = (ROOT / "amended" / CHANGED[3]).read_text()
assert 'TOP_RULE_SHA256 = "ce957fd86d5457f0e0a83fa726afa5aa4fbfd94d49471835dc83526ce3aa3b9d"' in test
assert "self.assertEqual(len(top.split()), 153)" in test
ptest = (ROOT / "proposed" / CHANGED[3]).read_text()
assert 'TOP_RULE_SHA256 = "71a852be0b5ebd2c3610e2d9952e01f4009939c49a9ac691d0f1e4e3f798ca7f"' in ptest
assert "self.assertEqual(len(top.split()), 144)" in ptest
for tree in ("base", "proposed", "amended"):
    for w in WITHHELD:
        p = ROOT / tree / w
        assert p.exists(), p
        shutil.rmtree(p) if p.is_dir() else p.unlink()
for tree in ("proposed", "amended"):
    got = sorted(differing(ROOT / "base", ROOT / tree))
    assert got == sorted(CHANGED), (tree, got)
hits = subprocess.run(["grep", "-rlE", r"prompt-audit-20260927|2026-09-27-prompt-audit-resolution", str(ROOT)],
                      capture_output=True, text=True).stdout.split()
print("files still naming the withheld paths:", sorted({re.sub(r"^.*?/root/[a-z]+/", "", h) for h in hits}))
print("root built:", sorted(p.name for p in ROOT.iterdir()))
