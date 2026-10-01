#!/usr/bin/env python3
"""Compare the sha256 values a receipt's provenance lists with the files of a checkout, and list scripts of the artifact directory that the receipt does not list.
usage: check_receipt_hashes.py <checkout> <receipt id>"""
import hashlib
import json
import sys
from pathlib import Path

root, rid = Path(sys.argv[1]), sys.argv[2]
receipt = json.loads((root / f"evidence/receipts/{rid}.json").read_text(encoding="utf-8"))
provenance = receipt["provenance"]
art = root / provenance["artifacts_dir"]
bad, checked = [], 0
for group, base in (("scripts_sha256", art), ("record_files_sha256", art), ("recorded_outputs_sha256", art / "recorded")):
    for name, digest in provenance[group].items():
        checked += 1
        path = base / name
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            bad.append((group, name))
listed = frozenset(provenance["scripts_sha256"])
print("provenance hashes checked:", checked, "| mismatches:", bad)
print("scripts in the directory but not in the receipt:", sorted(p.name for p in art.glob("*.py") if p.name not in listed))
