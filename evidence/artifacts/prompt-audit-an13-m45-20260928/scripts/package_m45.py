"""Write the M4/M5 convergence package: the frozen packet, sources, prompts, schemas, both lanes' returns and runner
records, the M5 adjudication (inputs, packets, prompts, returns, mapping, audit, tally) and the scripts.

usage: package_m45.py SCRATCH OUT
Host paths become placeholders: the private work directory <work>, the retired base worktree <base>, the
adjudication directory <adj>, the adjudication runner's directory <runs>, any other scratch path <scratch>, the home
directory ~ and the host user name <user>. The packet is copied byte for byte, and its hash is checked. The script
refuses to finish if a host path, the user name or an email address is left.
"""
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

S = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
W = S / ".hold3" / "convergence-m45"
ADJ = S / "m45-adj"
RUNS = S / "m45-adj-runs"
HOME = str(Path.home())
USER = Path.home().name
REPL = [
    (str(W), "<work>"), (str(S / "convergence-m45"), "<work>"), (str(S / "wt-m45-base"), "<base>"),
    (str(RUNS), "<runs>"), (str(ADJ), "<adj>"), (str(S), "<scratch>"), (HOME, "~"),
]


def clean(text):
    for a, b in REPL:
        text = text.replace(a, b)
    text = re.sub(r"/tmp/claude-\d+/[^\s\"'`)]*", "<scratch>", text)
    text = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<uuid>", text)
    return text.replace(USER, "<user>")


def put(rel, text):
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def copy_clean(src, rel):
    put(rel, clean(Path(src).read_text()))


def runner_record(src, rel):
    """A runner record saved from `codex_call.sh result <job>`, with host paths replaced."""
    put(rel, clean(Path(src).read_text()))


if OUT.exists():
    sys.exit(f"{OUT} exists")
OUT.mkdir(parents=True)

# First round: the frozen packet (byte for byte), the sources, the prompts, the schema and both returns.
packet = (W / "packet.md").read_bytes()
if hashlib.sha256(packet).hexdigest() != (W / "packet.sha256").read_text().split()[0]:
    sys.exit("packet.md changed after freezing")
if clean(packet.decode()) != packet.decode():
    sys.exit("the packet holds a host path")
(OUT / "round1").mkdir()
(OUT / "round1" / "packet.md").write_bytes(packet)
shutil.copy(W / "packet.sha256", OUT / "round1" / "packet.sha256")
copy_clean(W / "sources.json", "round1/sources.json")
copy_clean(W / "schemas" / "audit-judge-m45.json", "round1/schemas/audit-judge-m45.json")
for name in ("gpt6-probe.txt", "audit-judge-m45.txt", "claude-brief-m45.txt"):
    copy_clean(W / "prompts" / name, f"round1/prompts/{name}")
for name in ("gpt6-m45.json", "claude-m45.json", "round1-tally.json"):
    copy_clean(W / "returns" / name, f"round1/returns/{name}")
for job in ("gpt6-probe", "audit-judge-m45"):
    runner_record(W / "runner" / f"{job}.json", f"round1/runner/{job}.json")

# The M5 adjudication.
for d in ("adjudication-inputs", "packets", "prompts", "schemas"):
    for p in sorted((ADJ / d).iterdir()):
        copy_clean(p, f"adjudication/{d}/{p.name}")
shutil.copy(ADJ / "sent-sha256.json", OUT / "adjudication" / "sent-sha256.json")
for order in ("AB", "BA"):
    runner_record(W / "adjudication" / f"runner-m5-judge-{order}.json", f"adjudication/runner/m5-judge-{order}.json")
for name in ("gpt6.AB.json", "gpt6.BA.json", "claude.AB.json", "claude.BA.json", "m45-mapping.json",
             "tally-m45.json", "audit-control-m45.json"):
    copy_clean(W / "adjudication" / name, f"adjudication/{name}")
# The audit's hit windows quote the judges' session context, so the published copy keeps pattern, scope and match.
audit = json.loads((W / "adjudication" / "audit-m45.json").read_text())
for judgment in audit["judgments"].values():
    for hit in judgment["hits"] + judgment["info"]:
        hit["window"] = None
put("adjudication/audit-m45.json", clean(json.dumps(audit, ensure_ascii=False, indent=1)) + "\n")

# Scripts, as run, and the frozen hashes of the audit's inputs.
for name in ("build_packet_m45.py", "save_claude_return.py", "save_claude_judgment.py", "make_m5_adjudication.py", "void_patterns_m45.py", "audit_control_m45.py",
             "audit_m45.py", "tally_m45.py", "usage_m45.py", "package_m45.py", "frozen-sha256.txt",
             "isolation.log"):
    copy_clean(W / name, f"scripts/{name}")
copy_clean(W / "usage-m45.json", "usage.json")

# Refuse to finish on a leftover host path, the user name or an email address. This script's own copy is skipped: its
# patterns are the text this check looks for. The repository's pre-push scan covers it.
bad = re.compile(r"/home/|/Users/|/tmp/claude|" + re.escape(USER) + r"|[\w.+-]+@[\w-]+\.[\w.]+")
left = [str(p.relative_to(OUT)) for p in sorted(OUT.rglob("*"))
        if p.is_file() and p.name != "package_m45.py" and bad.search(p.read_text(errors="replace"))]
if left:
    sys.exit(f"host path, user name or email left in: {left}")
print(json.dumps({"files": sum(1 for p in OUT.rglob('*') if p.is_file()), "out": str(OUT.name)}))
