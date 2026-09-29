"""Build lane A's final round on X5a and X5c: the read-only lane roots, the packet, the Codex-strict schema and both
lanes' prompts. Round 1's build_lane_a.py, with each item's complete change and its measured checks.

usage: build_lane_a2.py
- root/base: main at 8315274f (git archive, no history); root/proposed: base plus the proposal's four files as
  measured in the X5 worktree (wt-x5); root/proposal.diff: that worktree's diff. The script asserts that base and
  proposed differ in exactly those four files.
- The measured results are the lines the checks printed (lane-a2/*.log and convergence-r3/x5c-*.log), with host
  paths replaced.
Writes k2/root, k2/packets/packet.md and packet.sha256, k2/schemas/lane.json, k2/prompts/gpt6-prompt.txt and
k2/prompts/claude-brief.txt.
"""
import filecmp
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

A2 = Path(__file__).resolve().parent
W3 = A2.parent
HOLD = W3.parent
S = HOLD.parent
K2 = S / "k2"
MAIN = Path.home() / "code/native-agent-stack"
BASE_REV = "8315274f"
WT = HOLD / "wt-x5"
CHANGED = ["adoption/templates/codex.AGENTS.template.md", "examples/claude-native/CLAUDE.md",
           "manifests/evidence.json", "tests/test_codex_worker_lane.py"]
ROOT = K2 / "root"
BASE, PROP = ROOT / "base", ROOT / "proposed"

assert not K2.exists(), "k2 already exists"
for d in ("packets", "prompts", "schemas", "work"):
    (K2 / d).mkdir(parents=True)
BASE.mkdir(parents=True)
arch = subprocess.run(["git", "-C", str(MAIN), "archive", BASE_REV], capture_output=True, check=True).stdout
subprocess.run(["tar", "-x", "-C", str(BASE)], input=arch, check=True)
shutil.copytree(BASE, PROP, symlinks=True)
for f in CHANGED:
    shutil.copyfile(WT / f, PROP / f)
diff = subprocess.run(["git", "-C", str(WT), "diff", "--", *CHANGED], capture_output=True, text=True,
                      check=True).stdout
(ROOT / "proposal.diff").write_text(diff)


def differing(a, b, rel=""):
    c = filecmp.dircmp(a, b)
    out = [f"{rel}{n}" for n in c.diff_files + c.left_only + c.right_only]
    for n, sub in c.subdirs.items():
        out += differing(Path(a) / n, Path(b) / n, f"{rel}{n}/")
    return out


got = sorted(differing(BASE, PROP))
assert got == sorted(CHANGED), got
item = {i["id"]: i for i in json.loads((W3 / "proposals.json").read_text())["items"]}
amend = {i["id"]: i for i in json.loads((W3 / "lane-a" / "gpt6.json").read_text())["items"]}
x5a_new = amend["X5a"]["resolution_text"]
x5c_new = item["X5c"]["new"]
assert (PROP / "examples/claude-native/CLAUDE.md").read_text().split("\n")[2] == x5a_new
assert (PROP / "adoption/templates/codex.AGENTS.template.md").read_text().split("\n")[2] == x5c_new
user_rule = (W3 / "user-level-top-rule.txt").read_text().strip()
SUBS = [(str(WT), "<worktree>"), ("<tmp>", "<tmp>"), (str(Path.home()), "~")]


def scrub(text):
    for old, new in SUBS:
        text = text.replace(old, new)
    return text


def lines(path, rx):
    return [scrub(ln) for ln in Path(path).read_text().splitlines() if re.search(rx, ln)]


def excerpt(path, start, end, tree=BASE):
    ls = (tree / path).read_text(encoding="utf-8").splitlines()
    body = "\n".join(f"{n:4d}: {ls[n - 1]}" for n in range(start, min(end, len(ls)) + 1))
    return f"`{path}:{start}-{min(end, len(ls))}`\n```\n{body}\n```\n"


def blame_date(path, line):
    out = subprocess.run(["git", "-C", str(MAIN), "log", "-1", "--format=%h %ad %s", "--date=short", "-L",
                          f"{line},{line}:{path}", BASE_REV], capture_output=True, text=True).stdout.splitlines()
    return out[0][:160] if out else "unknown"


def block(title, cmd, log, rx, exit_code):
    return (f"- {title}\n  Command (run from the worktree root): `{cmd}`\n"
            f"  Exit code: {exit_code}. Output lines:\n  ```\n  " + "\n  ".join(lines(log, rx)) + "\n  ```\n")


TOP = "tests.test_install_claude_profile.PortableTopRuleTests"
PIN = "tests.test_codex_worker_lane.TemplateTests.test_top_rule_and_upstream_text_are_verbatim"
TARGETED = ("tests.test_install_claude_profile tests.test_codex_worker_lane tests.test_codex_agents "
            "tests.test_codex_lane tests.test_landscape_sweep_harness tests.test_adoption_docs_consistency")
SUMMARY = r"^(Ran |OK|FAILED|FAIL:|ERROR:|AssertionError)"
measured = "".join([
    block("X5a failing control: line 3 set to the round-1 proposed text (quoted under X5a), which opens its second "
          "sentence with a capital 'Never'.", f"python3 -B -m unittest {TOP}", A2 / "x5a-control-roundone-text.log", SUMMARY,
          1),
    block("X5a proposed text in line 3.", f"python3 -B -m unittest {TOP}", A2 / "x5a-proposal-toprule.log", SUMMARY, 0),
    block("X5c failing control: the proposed line 3 with tests/test_codex_worker_lane.py at the base (no re-pin).",
          f"python3 -B -m unittest {PIN}", W3 / "x5c-control-template-only.log", SUMMARY, 1),
    block("X5c proposed line 3 with the re-pinned test.", f"python3 -B -m unittest {PIN}",
          W3 / "x5c-control-repinned.log", SUMMARY, 0),
    block("Registration control 1: both X5c files edited, manifest not yet re-registered.",
          "python3 scripts/validate.py", W3 / "x5c-validate-before-registration.log", r"\S", 1),
    block("Registration control 2: X5c files registered, X5a's template edited but not yet re-registered.",
          "python3 scripts/validate.py", A2 / "x5a-validate-before-registration.log", r"\S", 1),
    block("After registering all three changed files (scripts/host_receipts.py register_file; then "
          "scripts/component_matrix.py --write and scripts/new_host_grand_list.py --write, which changed nothing).",
          "python3 scripts/validate.py", A2 / "x5a-validate-after-registration.log", r"\S", 0),
    block("The complete proposal (root/proposed): the test modules that read either template or the pin.",
          f"python3 -B -m unittest {TARGETED}", A2 / "x5-proposal-targeted-tests.log", r"^(Ran |OK|FAILED)", 0),
])
x5a_ctrl = item["X5a"]["new"]
parts = [f"""# Judgment packet: prompt-audit lane A, final round: X5a and X5c (base 8315274f)

You are an independent reviewer. Two proposed changes to this repository's instruction templates are below, each
with every co-change it needs. Judge each on its merits: verify the evidence against the original files, check the
primary sources provided, research further where a claim depends on current official documentation, and decide
whether the proposed change is right.

Where things are (all read-only):
- `base/`: the repository at main 8315274f, a plain copy without git history (each line's last change is given
  below);
- `proposed/`: the same copy with this packet's complete proposal applied; it differs from `base/` in exactly four
  files: {", ".join(f"`{f}`" for f in CHANGED)};
- `proposal.diff`: the unified diff between them.

Rules:
- Verify, do not trust: excerpts below are copies; the files under `base/` and `proposed/` are the original source.
- A proposal that another file, test or fixture would contradict or break is wrong; say which, with file:line.
- Licenses and incumbency are never selection criteria.
- Judge wording on whether the target models (Claude Code and Codex sessions that load these files) will follow it as
  intended, not on style.
- These items carry the operator's own 2026-09-28 wording of the top rule into the repository's two templates of it.
  The operator's rule itself is not under review. Judge whether each proposed text carries that wording correctly and
  keeps the file's tested obligations and its existing meaning, and whether the co-changes are complete and correct.
- Every `sources` entry names a file:line or URL and quotes the text that supports your verdict.

Verdicts per item: `agree` = apply the proposed change exactly (line 3 and its co-changes); `amend` = apply your
`resolution_text` as line 3 instead, with the same co-changes recomputed for it by the same procedure; `reject` = keep
the current text and make no change. `resolution_text` is empty unless you amend. `confidence` is 0..1.

Convergence rule, fixed before either lane runs: an item is applied when both lanes agree, or when both give the same
amendment. Both reject: the current text stays. Anything else goes to one blind adjudication in both presentation
orders by two adjudicators, and a text is applied only when all four adjudications choose it. This is the final
round for both items: if it does not converge, the current text stays and both positions are recorded.

The operator's own user-level instruction file (`~/.claude/CLAUDE.md`, not in this repository; last modified
2026-09-28 07:34Z) opens with this top rule, verbatim:

```text
{user_rule}
```

The operator's direction for this pass (2026-09-28, verbatim): "please resolute cleanly with the sota repos
convergence,resolute all in your end and state the jobs that only beable to run by end,decide with your evidances and
sota repos evidances convergence".

---

## X5a: the portable Claude template's top rule

Location: `examples/claude-native/CLAUDE.md:3` (last changed by: {blame_date('examples/claude-native/CLAUDE.md', 3)}).

Current text: {item['X5a']['old']}

Proposed text: {x5a_new}

Co-change: re-register `examples/claude-native/CLAUDE.md` in `manifests/evidence.json` (docs/lanes.md:96-128); the
rest of the template, including steps 1-5 after line 3, is unchanged.

Why this text: the round-1 proposed text was "{x5a_ctrl}". It opens its second sentence with a capital "Never", which
the case-sensitive phrase check rejects (measured below). The proposed text keeps the operator's bold heading and
compounds sentence verbatim and keeps the tested phrase lowercase. It also keeps the installed client as a source of
truth: `docs/harness-defaults.md:58`, the section that calls itself the long form of this template's top rule,
names it too.

### Evidence
{excerpt('examples/claude-native/CLAUDE.md', 1, 12)}
{excerpt('tests/test_install_claude_profile.py', 915, 984)}
{excerpt('docs/harness-defaults.md', 7, 7)}
{excerpt('docs/harness-defaults.md', 56, 60)}
{excerpt('recipes/claude-native-profile.md', 79, 84)}
---

## X5c: the Codex user-instructions template's top rule

Location: `adoption/templates/codex.AGENTS.template.md:3` (last changed by:
{blame_date('adoption/templates/codex.AGENTS.template.md', 3)}).

Current text: {item['X5c']['old']}

Proposed text: {x5c_new}

Co-changes, all in `proposal.diff`:
- `tests/test_codex_worker_lane.py`: `TOP_RULE_SHA256` (:47) set to the sha256 of the proposed top-rule block, the
  word count at :210 from 120 to 144 and the :45 comment to match. Both values were computed with the test module's
  own `template_segments()` on the proposed template, not copied from elsewhere.
- `manifests/evidence.json`: the template and the test file re-registered (docs/lanes.md:96-128).
- Host step, outside the repository: a Codex home that installed the lane block keeps the old line until
  `tools/adoption/apply_codex_lane.py` is re-run there (dry run, then `--apply`) after the change merges.

Why the co-changes: `tests/test_codex_worker_lane.py:209-210` pin the staged top-rule block's sha256 and word count,
reproducing the 2026-09-26 staged block. Replacing line 3 alone fails that test (measured below).

### Evidence
{excerpt('adoption/templates/codex.AGENTS.template.md', 1, 9)}
{excerpt('tests/test_codex_worker_lane.py', 40, 50)}
{excerpt('tests/test_codex_worker_lane.py', 183, 212)}
{excerpt('tools/adoption/apply_codex_lane.py', 12, 15)}
{excerpt('evidence/artifacts/codex-worker-lane-20260926/scripts/assemble_agents.py.txt', 1, 6)}
{excerpt('docs/decisions/2026-09-26-codex-worker-lane.md', 57, 60)}
---

## Registration procedure (both items)
{excerpt('docs/lanes.md', 96, 128)}
---

## Measured results

Run by the coordinator on 2026-09-28 in one worktree of main 8315274f, at the stages each entry names; its final
state is the four files in `proposed/`. Test runs set TMPDIR to a private directory; the worktree path is shown as
`<worktree>`.

{measured}
---

## The complete proposal (`proposal.diff`)

```diff
{diff}```

---

## Primary sources

This round's questions are internal to the repository: its tests, pins, manifest and the two templates. How each
template reaches a session is recorded in the excerpts above: `recipes/claude-native-profile.md:79-84` for the
portable template, and `docs/decisions/2026-09-26-codex-worker-lane.md:57-58` for the Codex block, which cites the
Codex AGENTS.md guide as read on 2026-09-26. A lane with web access may re-check the current guides and cite them.
"""]
packet = "".join(parts)
(K2 / "packets" / "packet.md").write_text(packet)
sha = hashlib.sha256(packet.encode()).hexdigest()
(K2 / "packets" / "packet.sha256").write_text(f"{sha}  packet.md\n")

schema = {"type": "object", "additionalProperties": False, "required": ["items"], "properties": {"items": {
    "type": "array", "items": {"type": "object", "additionalProperties": False,
                               "required": ["id", "verdict", "resolution_text", "reasons", "sources", "confidence"],
                               "properties": {
                                   "id": {"type": "string", "enum": ["X5a", "X5c"]},
                                   "verdict": {"type": "string", "enum": ["agree", "amend", "reject"]},
                                   "resolution_text": {"type": "string"}, "reasons": {"type": "string"},
                                   "sources": {"type": "array", "items": {
                                       "type": "object", "additionalProperties": False,
                                       "required": ["locator", "quote"],
                                       "properties": {"locator": {"type": "string"}, "quote": {"type": "string"}}}},
                                   "confidence": {"type": "number"}}}}}}
(K2 / "schemas" / "lane.json").write_text(json.dumps(schema, indent=1) + "\n")
head = f"""Task: judge the 2 items in the packet below and answer only in the required JSON, one entry per item id.
- The lane root is {ROOT}: `base/` (main at 8315274f), `proposed/` (the complete proposal applied) and
  `proposal.diff`. Both are plain copies without git history. Read the original files there (for example sed -n, rg,
  diff -u; python3 -B runs a test module against a copy without writing). Do not write, install or change anything.
- You may search the web for current official documentation and maintained upstream repositories; cite them.
- Packet sha256: {sha}.

"""
(K2 / "prompts" / "gpt6-prompt.txt").write_text(head + packet)
brief = f"""Packet file: {K2 / 'packets' / 'packet.md'}
Repository root: {ROOT}

Task: judge the 2 items in the packet and return only one JSON object, one entry per item id, matching this schema:
{json.dumps(schema)}
The root holds `base/` (main at 8315274f), `proposed/` (the complete proposal applied) and `proposal.diff`; both
trees are plain copies without git history. You cannot run commands: the packet's measured results were run by the
coordinator, and you check them against the files. Packet sha256: {sha}.
"""
(K2 / "prompts" / "claude-brief.txt").write_text(brief)
print(sha, len(packet), "chars;", "prompt", len(head + packet), "bytes; brief", len(brief), "bytes; root differs in",
      got)
