"""Review repair (2026-09-28), one edit to the packager for the findings of the review round on the unpushed head:
- the GPT-6 review found three Claude subagent ids in six places of the published audit scripts. clean() now numbers
  each distinct id <agent-id-N> in order of first appearance, and write() refuses any id left over. The ids name
  transcript files in the host's private project store;
- the Claude review found that both adjudications' sent-sha256.json notes said the inputs and packet carry
  placeholders; only the prompts do;
- it also found attempt 1's GPT-6 usage unpublished: attempt1_usage.py reads it from the runner's event log without
  reading the returns;
- the review round itself (prompts, both reviews, usage and the repair's controls) is published under review/.
"""
from pathlib import Path

X = Path(__file__).resolve().parent
p = X.parent / "package_lane_a.py"
t = p.read_text()
pairs = [
    ('''RUNNER_KEYS = ("status",''',
     '''AGENT_ID = re.compile(r"\\ba[0-9a-f]{16}\\b")  # a Claude subagent id, as in agent-<id>.jsonl
AGENT_IDS = {}
RUNNER_KEYS = ("status",'''),
    ('''    text = re.sub(r"/tmp/claude-\\d+", "<tmp-root>", text)
    return''',
     '''    text = re.sub(r"/tmp/claude-\\d+", "<tmp-root>", text)
    text = AGENT_ID.sub(lambda m: AGENT_IDS.setdefault(m.group(0), f"<agent-id-{len(AGENT_IDS) + 1}>"), text)
    return'''),
    ('''    hits = [m.group(0) for m in PRIVATE.finditer(text) if m.group(0) != "noreply@anthropic.com"]''',
     '''    hits = [m.group(0) for m in PRIVATE.finditer(text) if m.group(0) != "noreply@anthropic.com"]
    hits += AGENT_ID.findall(text)'''),
    ('''"edit_package_6.py", "antipattern-rows.md"):''',
     '''"edit_package_6.py", "edit_package_7.py", "antipattern-rows.md"):'''),
    # both adjudications' notes: only the prompts carry placeholders; the inputs and packets are byte for byte
    ('''    "note": "sha256 of each file as the judges received it; the published inputs, packet and prompts replace host "
            "paths with <judges> and <root>.", "files": sent}))''',
     '''    "note": "sha256 of each file as the judges received it; the published prompts replace host paths with "
            "<judges> and <root>. The inputs, the packet and the schemas are byte for byte.", "files": sent}))'''),
    ('''    "note": "sha256 of each file as the judges received it; the published inputs, packet and prompts replace host "
            "paths with <judges> and <root>. root/proposal.diff''',
     '''    "note": "sha256 of each file as the judges received it; the published prompts replace host paths with "
            "<judges> and <root>. The inputs, the packet and the schema are byte for byte; root/proposal.diff'''),
    # attempt 1's GPT-6 usage, read from the runner's event log without the returns
    ('''copy(L / "make_adjudication_a.py", "adjudication/attempt1/make_adjudication_a.py")''',
     '''copy(L / "make_adjudication_a.py", "adjudication/attempt1/make_adjudication_a.py")
copy(AD / "attempt1-gpt6-usage.json", "adjudication/attempt1/gpt6-usage.json")
copy(AD / "attempt1_usage.py", "adjudication/attempt1/attempt1_usage.py")'''),
    # the review round and its repair
    ('''copy(AD / "README.lane-a.md", "README.md")''',
     '''copy(AD / "README.lane-a.md", "README.md")
for f in sorted((AD / "review").iterdir()):
    copy(f, f"review/{f.name}")'''),
]
for a, b in pairs:
    assert t.count(a) == 1, a[:60]
    t = t.replace(a, b)
p.write_text(t)
print("ok")
