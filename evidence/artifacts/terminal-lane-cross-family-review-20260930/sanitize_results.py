#!/usr/bin/env python3
"""Turn the private consolidated review results (collect_reviews.py output) into a publishable, sanitized JSON: absolute paths become placeholders, the host user name and scratch
directories are replaced, over-long fields are trimmed, and a count of replacements per pattern is reported (values are never printed).
usage: sanitize_results.py <consolidated.json> <out.json> [<extra-private-string> ...]"""
import json, re, sys
from pathlib import Path

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
extra = sys.argv[3:]
HOME = str(Path.home())
USER = Path.home().name
RULES = [
    (re.compile(re.escape(HOME + "/.local/state/native-agent-stack/terminal-lane-review-20260930/checkout")), "<checkout>"),
    (re.compile(re.escape(HOME + "/.local/state/native-agent-stack/terminal-lane-review-20260930")), "<work>"),
    (re.compile(r"/var/tmp/(?:rv|vf)-[A-Za-z0-9]+"), "<scratch>"),
    (re.compile(r"/tmp/(?:rv|vf)-[A-Za-z0-9]+"), "<scratch>"),
    (re.compile(re.escape(HOME)), "~"),
    (re.compile(r"\b" + re.escape(USER) + r"\b"), "<user>"),
    *[(re.compile(re.escape(item)), "<private>") for item in extra],
]
counts = {}


def clean(value):
    if isinstance(value, str):
        for number, (pattern, replacement) in enumerate(RULES):
            value, hits = pattern.subn(replacement, value)
            if hits:
                counts[replacement] = counts.get(replacement, 0) + hits
        return value
    if isinstance(value, list):
        return [clean(item) for item in value]
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    return value


data = clean(json.loads(src.read_text(encoding="utf-8")))
for finding in data.get("findings", []):
    for key in ("evidence", "failure_scenario", "fix", "claim"):
        if len(finding.get(key, "")) > 2500:
            finding[key] = finding[key][:2500] + " [trimmed]"
dst.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("wrote", dst.name, dst.stat().st_size, "bytes | replacements by placeholder:", counts)
leaks = [m for m in (HOME, USER) if m and m in dst.read_text(encoding="utf-8")]
print("residual home path or user name in the output:", bool(leaks))
