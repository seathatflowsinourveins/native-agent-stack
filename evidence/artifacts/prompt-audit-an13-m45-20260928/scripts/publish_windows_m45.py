"""Publish the text windows of the audit's hits, with host details replaced: the evidence that each hit is a false
positive. The published audit-m45.json keeps each hit's pattern, scope and match without its window. Only the two
Claude judgments have hits, and no judgment has a non-voiding record. The cleaning follows package_m45.py.

usage: publish_windows_m45.py PRIVATE_AUDIT SCRATCH OUT
Replaced: UUIDs (<uuid>); the adjudication directory (<adj>), including its tail after a truncated window start; the
scratch directory and any other path up to a scratchpad directory (<scratch>); the home directory (~); and the host
user name (<user>). Exits 1 if a host path, the user name or a UUID is left.
"""
import json
import re
import sys
from pathlib import Path

audit = json.loads(Path(sys.argv[1]).read_text())
S = str(Path(sys.argv[2]).resolve())
OUT = Path(sys.argv[3])
HOME, USER = str(Path.home()), Path.home().name
UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


def clean(text):
    text = re.sub(UUID, "<uuid>", text)
    text = text.replace(S + "/m45-adj", "<adj>").replace(S, "<scratch>")
    text = re.sub(r"\S*?/scratchpad/m45-adj\b", "<adj>", text)
    text = re.sub(r"\S*?/scratchpad\b", "<scratch>", text)
    text = text.replace(HOME, "~")
    text = re.sub(r"/tmp/claude-\d+/[^\s\"'`)]*", "<scratch>", text)
    return text.replace(USER, "<user>")


out = {"note": "Each hit of audit-m45.json with its window (80 characters either side of the match), host details "
               "replaced as the docstring of publish_windows_m45.py says.", "judgments": {}}
for name, judgment in audit["judgments"].items():
    if judgment["info"]:
        sys.exit(f"{name} has non-voiding records; this script publishes hits only")
    if judgment["hits"]:
        out["judgments"][name] = [{"pattern": h["pattern"], "scope": h["scope"], "match": h["match"],
                                   "window": clean(h["window"] or "")} for h in judgment["hits"]]
text = json.dumps(out, ensure_ascii=False, indent=1) + "\n"
if re.search(r"/home/|/Users/|/tmp/claude|" + re.escape(USER) + "|" + UUID, text):
    sys.exit("a host path, the user name or a UUID is left")
OUT.write_text(text)
print(json.dumps({k: len(v) for k, v in out["judgments"].items()}))
