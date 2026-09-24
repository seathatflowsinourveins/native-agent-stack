#!/usr/bin/env python3
"""Gold for the gap-15 tasks, computed outside any model over the frozen snapshot (41d39b3)."""
import json, re, sys
from pathlib import Path
root = Path(sys.argv[1])
counts = {str(p.relative_to(root)): sum(1 for l in p.read_text(encoding="utf-8").splitlines() if re.match(r"^\s*(async\s+)?def test_", l))
          for p in sorted((root / "tests").rglob("*.py"))}
top = max(counts, key=counts.get)
files = json.load(open(root / "manifests/evidence.json"))["files"]
rec = [f for f in files if f["path"].startswith("evidence/receipts/")]
print(json.dumps({"t1": {"total_test_functions": sum(counts.values()), "file_with_most": top, "file_with_most_count": counts[top]},
                  "t2": {"receipt_entries": len(rec), "receipt_bytes_total": sum(f["bytes"] for f in rec)}}))
