"""Write a wrong-answer copy of adoption/pins-macos-arm64.json for verify_pins.py's negative control.

Each of the seven hashed new pins (rtk, qmd, repomix, toon, ccusage, headroom, markitdown) gets a
sha256 that is not its artifact's (the sha256 of the text "negative-control:<id>"), and serena gets
a well-formed 40-hex commit that is not its pinned one (the last hex digit of the real commit
advanced by one). Nothing else changes, so verify_pins.py must report every hash comparison against
these pins as a MISMATCH and fail on serena's commit, then exit nonzero.

Usage: python3 negative_control.py <pins-macos-arm64.json> <output directory>
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HASHED_IDS = ("rtk", "qmd", "repomix", "toon", "ccusage", "headroom", "markitdown")

source, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
pins = json.loads(source.read_text(encoding="utf-8"))
by_id = {tool["id"]: tool for tool in pins["tools"]}
for tool_id in HASHED_IDS:
    wrong = hashlib.sha256(f"negative-control:{tool_id}".encode()).hexdigest()
    assert wrong != by_id[tool_id]["sha256"]
    by_id[tool_id]["sha256"] = wrong
    print(f"{tool_id}: sha256 -> {wrong}")
serena = by_id["serena"]
wrong_commit = serena["commit"][:-1] + format((int(serena["commit"][-1], 16) + 1) % 16, "x")
assert wrong_commit != serena["commit"] and len(wrong_commit) == 40
serena["commit"] = wrong_commit
print(f"serena: commit -> {wrong_commit}")
out_dir.mkdir(parents=True, exist_ok=True)
target = out_dir / source.name
target.write_text(json.dumps(pins, indent=2) + "\n", encoding="utf-8")
print(f"wrote {target.name} sha256 {hashlib.sha256(target.read_bytes()).hexdigest()}")
