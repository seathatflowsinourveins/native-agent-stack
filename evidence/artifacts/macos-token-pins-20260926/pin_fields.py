"""Which fields differ between two copies of a pins file, and whether verify_pins.py reads any of them.

Usage, from the repository root:
  python3 evidence/artifacts/macos-token-pins-20260926/pin_fields.py <label>=<old.json> <label>=<new.json>

Prints each copy's sha256, every top-level key and every tool field whose value differs between the
two copies, and then whether any differing field is one verify_pins.py reads. verify_pins.py reads
only these pin fields: version, kind, url, sha256, commit and package (the macOS and the Linux
entries of rtk, qmd, repomix, toon, ccusage, headroom, markitdown and serena), checksum_ref of the
four macOS npm pins (it must quote dist.integrity) and install_note of the macOS markitdown pin (it
must quote the wheel sha256). A copy that differs only elsewhere gives the same verify_pins.py
result against the same upstream artifacts. The same field sets are applied to a Linux pair, which
can only over-report: verify_pins.py reads no prose field of the Linux entries. Labels, not paths,
are printed. Exits 1 when a field verify_pins.py reads differs.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

CHECKED_IDS = ("rtk", "qmd", "repomix", "toon", "ccusage", "headroom", "markitdown", "serena")
READ_FIELDS = {"version", "kind", "url", "sha256", "commit", "package"}
READ_PROSE = {("qmd", "checksum_ref"), ("repomix", "checksum_ref"), ("toon", "checksum_ref"),
              ("ccusage", "checksum_ref"), ("markitdown", "install_note")}


def load(argument: str) -> tuple[str, bytes, dict]:
    label, _, path = argument.partition("=")
    data = Path(path).read_bytes()
    return label, data, json.loads(data)


(old_label, old_bytes, old), (new_label, new_bytes, new) = (load(argument) for argument in sys.argv[1:3])
print(f"{old_label}: sha256 {hashlib.sha256(old_bytes).hexdigest()}")
print(f"{new_label}: sha256 {hashlib.sha256(new_bytes).hexdigest()}")
changed: list[tuple[str | None, str]] = []
for key in sorted(set(old) | set(new)):
    if key != "tools" and old.get(key) != new.get(key):
        changed.append((None, key))
old_tools = {tool["id"]: tool for tool in old["tools"]}
new_tools = {tool["id"]: tool for tool in new["tools"]}
if list(old_tools) != list(new_tools):
    print(f"tool ids or their order differ: {list(old_tools)} -> {list(new_tools)}")
    changed.append((None, "tools"))
for tool_id in [tool_id for tool_id in old_tools if tool_id in new_tools]:
    for field in sorted(set(old_tools[tool_id]) | set(new_tools[tool_id])):
        if old_tools[tool_id].get(field) != new_tools[tool_id].get(field):
            changed.append((tool_id, field))
for tool_id, field in changed:
    print(f"changed: {field}" if tool_id is None else f"changed: tools[{tool_id}].{field}")
read = [(tool_id, field) for tool_id, field in changed
        if tool_id is None and field == "tools"
        or tool_id in CHECKED_IDS and (field in READ_FIELDS or (tool_id, field) in READ_PROSE)]
print(f"{len(changed)} changed field(s); read by verify_pins.py: "
      + (", ".join(f"tools[{tool_id}].{field}" if tool_id else field for tool_id, field in read) if read else "none"))
sys.exit(1 if read else 0)
