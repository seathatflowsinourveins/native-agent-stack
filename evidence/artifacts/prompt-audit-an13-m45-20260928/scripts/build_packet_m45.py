"""Build the frozen M4/M5 judgment packet, the shared sources, the schema and both lanes' prompts.

usage: build_packet_m45.py BASE_WORKTREE REPORT_MD OLD_SOURCES_JSON UPSTREAM_SKILL_MD
Writes packet.md, sources.json, schemas/audit-judge-m45.json, prompts/audit-judge-m45.txt,
prompts/claude-brief-m45.txt and packet.sha256 next to this script.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

W = Path(__file__).resolve().parent
base, report_md, old_sources, upstream_skill = (Path(p).resolve() for p in sys.argv[1:5])
report = report_md.read_text().splitlines()
IDS = ["M4", "M5"]


def excerpt(rel, a, b):
    lines = (base / rel).read_text().splitlines()
    body = "\n".join(f"{n:4}: {lines[n - 1]}" for n in range(a, min(b, len(lines)) + 1))
    return f"`{rel}:{a}-{b}`\n```\n{body}\n```"


def blame(rel, a, b):
    out = subprocess.run(["git", "-C", str(base), "blame", "--porcelain", "-L", f"{a},{b}", "--", rel],
                         capture_output=True, text=True, check=True).stdout.splitlines()
    seen, rows = set(), []
    info = {}
    for line in out:
        parts = line.split(" ")
        if len(parts[0]) == 40 and all(c in "0123456789abcdef" for c in parts[0]):
            current = parts[0]
            info.setdefault(current, {})
        elif line.startswith("author-time "):
            info[current]["time"] = int(line.split(" ", 1)[1])
        elif line.startswith("summary "):
            info[current]["summary"] = line.split(" ", 1)[1]
    import datetime
    for sha, d in info.items():
        if sha in seen:
            continue
        seen.add(sha)
        day = datetime.datetime.fromtimestamp(d.get("time", 0), datetime.timezone.utc).date().isoformat()
        rows.append(f'{sha[:8]} {day} "{d.get("summary", "")}"')
    return f"git blame `{rel}:{a}-{b}`: " + "; ".join(rows)


def report_lines(a, b):
    return "\n".join(report[a - 1:b])


upstream_bytes = upstream_skill.read_bytes()
upstream_sha = hashlib.sha256(upstream_bytes).hexdigest()
assert upstream_sha.startswith("2befe7fc55bcadaa"), upstream_sha
sources_path = W / "sources.json"
skill_copy = W / "sources" / "verification-before-completion-8ca22dba.SKILL.md"
skill_copy.write_bytes(upstream_bytes)

old = json.loads(old_sources.read_text())
old_items = old if isinstance(old, list) else old.get("sources", old)
kept = [s for s in (old_items if isinstance(old_items, list) else list(old_items.values()))
        if isinstance(s, dict) and s.get("id") in {f"S{i}" for i in range(1, 11)}]
new_sources = kept + [
    {
        "id": "U1",
        "url": "https://github.com/obra/superpowers/blob/8ca22dba9a94f28898bbce59f2537ff4d87c747d/skills/verification-before-completion/SKILL.md",
        "retrieved": "2026-09-28",
        "note": f"The pinned upstream file, copied byte for byte to {skill_copy}. sha256 {upstream_sha}, {len(upstream_bytes)} bytes, which equals the adoption manifest's skill_md_sha256 and the installed user-level copy's sha256 on this host. The GitHub contents API gives the same blob (7d45333cc4a4) at 8ca22dba and on upstream main on 2026-09-28, so the pin is upstream's current file.",
        "quote": "",
    },
    {
        "id": "U2",
        "url": "https://github.com/obra/superpowers/commit/3be5aad3dd24",
        "retrieved": "2026-09-28",
        "note": "The latest upstream commit that touches skills/verification-before-completion/SKILL.md (committed 2026-07-24), from the GitHub commits API filtered by path. The two earlier ones are 2025-10-17 and 2025-10-16.",
        "quote": "refactor(skills): drop persuasion sections from verification-before-completion\n\nWhy This Matters (failure-memory testimonials), the dishonesty reframing\nin the Overview, and The Bottom Line recap all restate stakes the Iron\nLaw, gate function, and rationalization table already enforce. This is\nthe eval-gated class: the bet is that discipline holds without the\npersuasion prose — evals on this branch decide.",
    },
    {
        "id": "U3",
        "url": "https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5.md",
        "retrieved": "2026-09-28",
        "note": "Section 'Task scope and over-verification'. The session model of this repository's coordinator and builder is Opus 5.5; its own guide is at https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5.md.",
        "quote": "Claude Opus 5 verifies its own work without being told to. If your prompt contains explicit verification instructions (\"include a final verification step for any non-trivial task,\" \"use a subagent to verify\"), remove them: instructions like these cause over-verification on Claude Opus 5, and removing them reduces wasted tokens with no loss in quality. The same applies to legacy harness scaffolding that adds separate verification steps.",
    },
]
sources_path.write_text(json.dumps({"sources": new_sources}, indent=1, ensure_ascii=False) + "\n")

head = subprocess.run(["git", "-C", str(base), "rev-parse", "--short=8", "HEAD"], capture_output=True, text=True,
                      check=True).stdout.strip()

packet = f"""# Judgment packet: two findings left from a headless prompt-audit run (frozen at {head})

You are an independent reviewer. A headless prompt-audit run over this repository (its client's own audit command)
reported the two findings below with proposed rewrites. Nobody else has judged them yet. Judge each on its merits:
verify the evidence against the original source (the repository is checked out read-only at the base path in your
task), check the shared primary sources, research further where a claim depends on current official documentation or
on the upstream project, and decide whether the proposed rewrite is right.

Rules:
- Verify, do not trust: excerpts below are copies; the files at the base path and the upstream URLs are the original
  source.
- A proposal that another file, test, pin or fixture would contradict or break is wrong; say which.
- Keep the operator's standing rules: the current upstream state of a maintained source is the source of truth, and a
  vendored upstream file is changed by re-pinning to an upstream revision, not by a local edit; licenses and
  incumbency are never selection criteria.
- Judge wording on whether the target models will follow it as intended, not on style.
- A change whose effect on behavior is unmeasured may still be right, but say what would show it wrong.
- Every `sources` entry names a file:line or URL and quotes the text that supports your verdict.

Verdicts per item: `agree`, `amend` or `reject`, with the meaning stated in each item. `resolution_text` holds the
exact edit for `amend` and is empty otherwise. `confidence` is 0..1.

---

## M4: pressure wording and broad triggers in a vendored skill that the builder agent preloads

Location: the user-level skill `verification-before-completion` (vendored from `obra/superpowers`, installed for all
projects and shared with the second coding client), and its preload in `.claude/agents/isolated-builder.md:9`.

Verdict meaning: agree = apply hunks D1-D3 below to the vendored user-level skill exactly as written; amend = apply the
exact edit you give in resolution_text instead (name every file and give the exact text; it may change project files,
for example the builder's preload list or the skill's adoption status, instead of the vendored skill); reject = change
no file for this item in this unit.

### The finding, as the audit reported it
{report_lines(81, 94)}

### The audit's proposed rewrite (hunks D1-D3, against the installed copy)
{report_lines(150, 231)}

### Evidence
The installed copy is byte-identical to the pin: sha256 `{upstream_sha}` ({len(upstream_bytes)} bytes), the same as
source U1, which holds a copy of the upstream file at the pin. Upstream's own history of this file is source U2.

{excerpt("adoption/skills/manifest.json", 315, 339)}
{blame("adoption/skills/manifest.json", 316, 338)}

{excerpt(".claude/agents/isolated-builder.md", 1, 10)}
{blame(".claude/agents/isolated-builder.md", 9, 9)}
`adoption/agents/claude/isolated-builder.md:9` and `examples/claude-native/agents/isolated-builder.md:9` carry the same
preload.

{excerpt("examples/claude-native/workflows/test-contract-mutations.mjs", 68, 73)}
{blame("examples/claude-native/workflows/test-contract-mutations.mjs", 70, 71)}

{excerpt("adoption/bootstrap.md", 343, 349)}

{excerpt("docs/decisions/2026-09-26-stack-agents-role-dispatch.md", 43, 51)}

### Constraints
- The adoption manifest pins the skill by upstream ref, tree and `skill_md_sha256`; a local edit breaks that pin and a
  skills update from upstream would undo it.
- The builder's preloads are a reviewed contract that the workflow contract mutations pin
  (`test-contract-mutations.mjs:70-73`: removing or substituting a preload must fail the suite).
- The same user-level skill is enabled for the second coding client (`codex_enabled: true`).

---

## M5: a history narrative in place of a rule, in a nested application's instruction file

Location: `blueprints/convergence-practice/application-delivery/AGENTS.md:15-18`

Verdict meaning: agree = replace lines 15-18 with hunk E's three lines exactly; amend = replace lines 15-18 with your
exact resolution_text instead; reject = keep lines 15-18 unchanged.

### The finding, as the audit reported it
{report_lines(96, 100)}

### The audit's proposed rewrite (hunk E)
{report_lines(233, 244)}

### Evidence
{excerpt("blueprints/convergence-practice/application-delivery/AGENTS.md", 1, 18)}
{blame("blueprints/convergence-practice/application-delivery/AGENTS.md", 15, 18)}

`blueprints/convergence-practice/application-delivery/CLAUDE.md` is the single line `@AGENTS.md`.

### Constraints
- No test, receipt, freeze record or fixture in the repository quotes or hashes this file's text, except the evidence
  manifest, which records its sha256 and byte count (`scripts/validate.py:376-387`); an edit is re-registered there.
- The file is the nested contract of a qualified application slice (`blueprints/convergence-practice/application-delivery/README.md`).
"""
(W / "packet.md").write_text(packet)
packet_sha = hashlib.sha256(packet.encode()).hexdigest()
(W / "packet.sha256").write_text(f"{packet_sha}  packet.md\n")

schema = {
    "type": "object", "additionalProperties": False, "required": ["items"],
    "properties": {"items": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["id", "verdict", "resolution_text", "reasons", "sources", "confidence"],
        "properties": {
            "id": {"type": "string", "enum": IDS},
            "verdict": {"type": "string", "enum": ["agree", "amend", "reject"]},
            "resolution_text": {"type": "string"},
            "reasons": {"type": "string"},
            "sources": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["locator", "quote"],
                "properties": {"locator": {"type": "string"}, "quote": {"type": "string"}}}},
            "confidence": {"type": "number"}}}}}}
(W / "schemas" / "audit-judge-m45.json").write_text(json.dumps(schema, indent=1) + "\n")

gpt_prompt = f"""Task: judge the 2 items in the packet below and answer only in the required JSON, one entry per item id.
- The repository is checked out read-only at {base} (main at {head}). Read the original files there (for example
  sed -n, rg, git -C {base} log/blame/show). Do not write, install or change anything.
- Primary sources with verbatim quotes, gathered for this task, are in {sources_path}; source U1's copy of the upstream
  skill is {skill_copy}. You may search the web for current official documentation and the upstream repository;
  cite official or upstream sources only.
- Packet sha256: {packet_sha}.

{packet}"""
(W / "prompts" / "audit-judge-m45.txt").write_text(gpt_prompt)

claude_brief = f"""Task: judge the 2 items in the judgment packet and answer only in the required JSON, one entry per item id.
- Read the packet in full: {W / "packet.md"} (sha256 {packet_sha}). It states the rules and, for each item, the evidence, the proposed rewrite, the constraints and what each verdict means.
- Then read the shared primary sources: {sources_path}, and source U1's copy of the upstream skill: {skill_copy}.
- The repository is checked out read-only at {base} (main at {head}). Verify the packet's excerpts and claims against the original files there with Read, Grep and Glob. You have no shell or web access; rely on the repository and the sources file. Do not write or change anything.
- Return only a JSON object that validates against {W / "schemas" / "audit-judge-m45.json"}: {{"items": [{{"id", "verdict", "resolution_text", "reasons", "sources": [{{"locator", "quote"}}], "confidence"}}]}}, with exactly one entry per id (M4, M5). verdict is agree, amend or reject; resolution_text holds the exact edit for amend and is empty otherwise; confidence is 0..1. No prose outside the JSON.
"""
(W / "prompts" / "claude-brief-m45.txt").write_text(claude_brief)
print(json.dumps({"packet_sha256": packet_sha, "packet_bytes": len(packet.encode()), "sources": len(new_sources),
                  "gpt_prompt_bytes": len(gpt_prompt.encode()), "head": head}))
