#!/usr/bin/env python3
"""Generate results.json for the layer from the receipts themselves (never by hand)."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LAYER = ROOT / "evidence/artifacts/gap-wave2-20260923/foundation__scheduling-supervision"


def main():
    results = {}
    for path in sorted(LAYER.glob("*.json")):
        if path.name == "results.json":
            continue
        receipt = json.loads(path.read_text())
        if "gap_index" not in receipt or "outcome" not in receipt:
            continue
        key = str(receipt["gap_index"])
        if key in results:
            raise SystemExit(f"Two receipts claim gap {key}")
        results[key] = {"outcome": receipt["outcome"], "receipt": str(path.relative_to(ROOT))}
    ordered = {k: results[k] for k in sorted(results, key=int)}
    out = {"layer_id": "scheduling-supervision", "catalog": "foundation", "wave": "gap-wave2-20260923",
           "generated_by": "blueprints/gap-wave2-20260923/foundation__scheduling-supervision/make_results.py",
           "results": ordered}
    (LAYER / "results.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({k: v["outcome"] for k, v in ordered.items()}))


if __name__ == "__main__":
    main()
