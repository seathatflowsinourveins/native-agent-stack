#!/usr/bin/env python3
"""Corrected analysis of the already-retained difft 0.71.0 per-file reports at
$HOME/codex-ecosystem/state/gap-resolution-20260922/worktrunk/difft-out/reports/.

This does NOT re-invoke difft and does NOT re-run the 20 diff commands recorded
in results.jsonl / results-corrected.jsonl's "cmd" provenance -- it only fixes a
bug in the original detection logic in run_difft.sh, which grepped report bodies
for "failed to parse|could not find a parser|panicked" and never matched
difftastic's actual fallback header, e.g.:

    <path> --- Text
    <path> --- 1/29 --- Text (exceeded DFT_GRAPH_LIMIT)
    <path> --- Text (12.6 MiB exceeded DFT_BYTE_LIMIT)

vs. a real structural parse, e.g.:
    <path> --- JSON
    <path> --- 1/2 --- Python

Per the fix-round rule ("do NOT re-run a check to obtain a different outcome ...
only if the finding says the procedure itself was wrong, run the corrected
procedure once"): the finding here says the detection procedure (not the difft
invocation) was wrong, so this script reprocesses the SAME raw report bytes
already on disk from the one difft run on 2026-09-22, using the corrected
detection rule, and writes results-corrected.jsonl alongside the original
results.jsonl (which is left untouched as the original raw artifact).
"""
import hashlib
import json
import re
from pathlib import Path

REPORTS = Path("$HOME/codex-ecosystem/state/gap-resolution-20260922/worktrunk/difft-out/reports").expanduser()
REPORTS = Path(str(REPORTS).replace("$HOME", str(Path.home())))
OUT = REPORTS.parent / "results-corrected.jsonl"

# difftastic's real header line looks like one of:
#   "<path> --- <Lang>"
#   "<path> --- <n>/<m> --- <Lang>"
# where <Lang> in {JSON, Python, Text, ...}. "Text" is difftastic's own fallback
# language name for "no specific parser used / fell back to line diff", used both
# for genuinely unparseable types (no .md grammar) and for parseable types that
# exceeded a size/graph limit (DFT_BYTE_LIMIT, DFT_GRAPH_LIMIT).
HEADER_RE = re.compile(r"^\S.* --- (?:\d+/\d+ --- )?([A-Za-z][A-Za-z0-9+]*)\b")

rows = []
for report_path in sorted(REPORTS.glob("*.txt")):
    text = report_path.read_text(errors="replace")
    first_line = text.splitlines()[0] if text else ""
    m = HEADER_RE.match(first_line)
    lang = m.group(1) if m else None
    fell_back_to_text = (lang == "Text")
    parsed_structurally = lang is not None and not fell_back_to_text
    rows.append({
        "report_file": report_path.name,
        "header_line": first_line,
        "detected_language": lang,
        "parsed_structurally": parsed_structurally,
        "fell_back_to_text": fell_back_to_text,
        "output_bytes": len(text.encode("utf-8")),
    })

with OUT.open("w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")

parsed = sum(1 for r in rows if r["parsed_structurally"])
fallback = sum(1 for r in rows if r["fell_back_to_text"])
unknown = sum(1 for r in rows if r["detected_language"] is None)
print(f"total={len(rows)} parsed_structurally={parsed} fell_back_to_text={fallback} unknown={unknown}")
print("fallback files:")
for r in rows:
    if r["fell_back_to_text"]:
        print(f"  {r['report_file']}: {r['header_line']}")
print("sha256(results-corrected.jsonl) =", hashlib.sha256(OUT.read_bytes()).hexdigest())
