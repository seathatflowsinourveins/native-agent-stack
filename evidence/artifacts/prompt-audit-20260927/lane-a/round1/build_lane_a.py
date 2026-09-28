"""Build round 3's lane-A packet (S1, X5a, X5b, X5c), the GPT-6 prompt, the Claude brief and the Codex-strict schema.

usage: build_lane_a.py
Reads the proposals (proposals.json), the facts gathered from the live GitHub API (facts-s1.json), the user-level
top rule (user-level-top-rule.txt, copied verbatim from ~/.claude/CLAUDE.md line 5) and the primary sources
(sources-r3.json), and excerpts every repository file from the read-only base worktree with its line numbers.
Writes lane-a/packet.md, lane-a/packet.sha256, lane-a/gpt6-prompt.txt, lane-a/claude-brief.txt and
lane-a/schema.json. Adapted from the round-1 packet (convergence-prompt-audit/build_packet.py).
"""
import hashlib
import json
import subprocess
from pathlib import Path

W = Path(__file__).resolve().parent
S = W.parent
BASE = S / "wt-r3-base"
OUT = W / "lane-a"
OUT.mkdir(exist_ok=True)
proposals = json.loads((W / "proposals.json").read_text())["items"]
facts = json.loads((W / "facts-s1.json").read_text())
user_rule = (W / "user-level-top-rule.txt").read_text().strip()
sources = json.loads((W / "sources-r3.json").read_text())


def excerpt(path, start, end):
    lines = (BASE / path).read_text(encoding="utf-8").splitlines()
    body = "\n".join(f"{n:4d}: {lines[n - 1]}" for n in range(start, min(end, len(lines)) + 1))
    return f"`{path}:{start}-{end}`\n```\n{body}\n```\n"


def blame_date(path, line):
    out = subprocess.run(["git", "-C", str(BASE), "log", "-1", "--format=%h %ad %s", "--date=short", "-L",
                          f"{line},{line}:{path}"], capture_output=True, text=True).stdout.splitlines()
    return out[0][:160] if out else "unknown"


P = {p["id"]: p for p in proposals}
parts = [f"""# Judgment packet: prompt-audit round 3, lane items S1 and X5a-c (frozen at 46184751)

You are an independent reviewer. Four proposed edits to this repository's instruction files are below. Judge each on
its merits: verify the evidence against the original files (the repository is checked out read-only at the base path
in your task), check the primary sources provided, research further where a claim depends on current official
documentation, and decide whether the proposed text is right.

Rules:
- Verify, do not trust: excerpts below are copies; the files at the base path are the original source.
- A proposal that another file, test or fixture would contradict or break is wrong; say which, with file:line.
- Licenses and incumbency are never selection criteria.
- Judge wording on whether the target models (Claude Code and Codex sessions that load these files) will follow it as
  intended, not on style.
- X5a-c carry the operator's own 2026-09-28 wording of the top rule into the repository's three copies of it. The
  operator's rule itself is not under review. Judge whether each proposed text carries that wording correctly and
  keeps the file's tested obligations and its existing meaning.
- Every `sources` entry names a file:line or URL and quotes the text that supports your verdict.

Verdicts per item: `agree` = apply the proposed text exactly; `amend` = apply your `resolution_text` instead (the exact
replacement for the proposal's `old` text); `reject` = keep the current text. `resolution_text` is empty unless you
amend. `confidence` is 0..1.

Convergence rule, fixed before either lane runs: an item is applied when both families agree, or when both give the
same amendment. Both reject: the current text stays. Anything else goes to one blind adjudication in both
presentation orders, and a text is applied only when all four adjudications choose it.

---
"""]

s1 = P["S1"]
parts.append(f"""## S1: a PR-description sentence in AGENTS.md

Location: {s1['file']}:37 at {s1['at'].split(' ')[0]}. Proposed by another session of this repository on
2026-09-28, from its practice sweep.

Current text (end of line 37): {s1['old']}

Proposed text: {s1['new']}

### Evidence
{excerpt('AGENTS.md', 35, 38)}
{excerpt('.github/workflows/validate.yml', 316, 341)}
{excerpt('.github/pull_request_template.md', 5, 14)}
Facts read from the live GitHub API on {facts['date']} (read-only calls; commands as run):
""")
for f in facts["facts"]:
    parts.append(f"- {f['fact']} (`{f['command']}`)\n")
parts.append("\n---\n")

x5a = P["X5a"]
parts.append(f"""## X5a: the portable Claude template's top rule

Location: {x5a['file']}:3 (last changed by: {blame_date(x5a['file'], 3)}).

Current text: {x5a['old']}

Proposed text: {x5a['new']}

The rest of the template, including the numbered steps 1-5 that follow line 3, is unchanged.

### Evidence
{excerpt(x5a['file'], 1, 12)}
{excerpt('tests/test_install_claude_profile.py', 915, 965)}
{excerpt('recipes/claude-native-profile.md', 79, 84)}
The operator's own user-level instruction file (`~/.claude/CLAUDE.md`, not in this repository; last modified
2026-09-28 07:34Z) opens with this top rule, verbatim:

```text
{user_rule}
```

The operator's direction for this pass (2026-09-28, verbatim): "please resolute cleanly with the sota repos
convergence,resolute all in your end and state the jobs that only beable to run by end,decide with your evidances and
sota repos evidances convergence".

Round 1 of this audit (docs/decisions/2026-09-27-prompt-audit-resolution.md, item X5) recorded that the template's top
rule differs from the host's user-level file and left it to the operator.

---
""")

x5b = P["X5b"]
parts.append(f"""## X5b: AGENTS.md's top rule

Location: {x5b['file']}:3 (last changed by: {blame_date(x5b['file'], 3)}).

Current text: {x5b['old']}

Proposed text: {x5b['new']}

The proposed text is the user-level top rule quoted under X5a, verbatim.

### Evidence
{excerpt('AGENTS.md', 1, 4)}
Round 1 of this audit (item X5, both lanes agree) left `AGENTS.md:3` unedited, because it and the template's rule
overlap and "the broader rule covers the narrower one"; that judgment did not concern the operator's later wording.
`AGENTS.md` is read by Codex and Claude Code sessions in this repository, and `CLAUDE.md` imports it (`@AGENTS.md`).

---
""")

x5c = P["X5c"]
parts.append(f"""## X5c: the Codex user-instructions template's top rule

Location: {x5c['file']}:3 (last changed by: {blame_date(x5c['file'], 3)}).

Current text: {x5c['old']}

Proposed text: {x5c['new']}

### Evidence
{excerpt(x5c['file'], 1, 9)}
{excerpt('tools/adoption/apply_codex_lane.py', 12, 15)}
{excerpt('tests/test_codex_worker_lane.py', 194, 205)}
---

## Primary sources gathered for round 3

Each entry: source, date retrieved, verbatim quote, and the claim it supports.
""")
for q in sources["questions"]:
    if q["id"] not in ("Q3",):
        continue
    parts.append(f"\n### {q['title']}\n")
    for s in q["findings"]:
        parts.append(f"- {s['source']} ({s['date']}): \"{s['quote']}\" Supports: {s['claim']}\n")
    for n in q.get("not_found", []):
        parts.append(f"- Not found: {n}\n")

packet = "".join(parts)
(OUT / "packet.md").write_text(packet)
sha = hashlib.sha256(packet.encode()).hexdigest()
(OUT / "packet.sha256").write_text(f"{sha}  packet.md\n")

schema = {"type": "object", "additionalProperties": False, "required": ["items"], "properties": {"items": {
    "type": "array", "items": {"type": "object", "additionalProperties": False,
                               "required": ["id", "verdict", "resolution_text", "reasons", "sources", "confidence"],
                               "properties": {
                                   "id": {"type": "string", "enum": ["S1", "X5a", "X5b", "X5c"]},
                                   "verdict": {"type": "string", "enum": ["agree", "amend", "reject"]},
                                   "resolution_text": {"type": "string"}, "reasons": {"type": "string"},
                                   "sources": {"type": "array", "items": {
                                       "type": "object", "additionalProperties": False,
                                       "required": ["locator", "quote"],
                                       "properties": {"locator": {"type": "string"}, "quote": {"type": "string"}}}},
                                   "confidence": {"type": "number"}}}}}}
(OUT / "schema.json").write_text(json.dumps(schema, indent=1) + "\n")

head = f"""Task: judge the 4 items in the packet below and answer only in the required JSON, one entry per item id.
- The repository is checked out read-only at {BASE} (PR #444's head, 46184751). Read the original files there
  (for example sed -n, rg, git -C {BASE} log/blame/show). Do not write, install or change anything.
- You may search the web for current official documentation and maintained upstream repositories; cite them.
- Packet sha256: {sha}.

"""
(OUT / "gpt6-prompt.txt").write_text(head + packet)
(OUT / "claude-brief.txt").write_text(head.replace("answer only in the required JSON",
                                                   "return only the required JSON (schema at "
                                                   f"{OUT / 'schema.json'})") + packet)
print(sha, len(packet), "chars")
