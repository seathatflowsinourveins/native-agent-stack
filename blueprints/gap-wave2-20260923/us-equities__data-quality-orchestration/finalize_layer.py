"""Refresh every receipt's raw_artifacts sha256 from the committed bytes, fail
if a cited artifact is missing, and generate results.json (gap_index ->
outcome, receipt) from the receipts themselves, never by hand.

  finalize_layer.py <layer-evidence-dir>
"""
import hashlib
import json
import sys
from pathlib import Path


def main():
    layer = Path(sys.argv[1])
    repo = layer.parents[3]
    results = {}
    for path in sorted(layer.glob("[0-9]*-*.json")):
        receipt = json.loads(path.read_text())
        for art in receipt.get("raw_artifacts", []):
            data = (repo / art["path"]).read_bytes()  # raises if missing
            art["sha256"] = hashlib.sha256(data).hexdigest()
            art["bytes"] = len(data)
        path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
        if receipt["outcome"] == "pending":
            raise SystemExit(f"{path.name}: outcome still pending")
        results[str(receipt["gap_index"])] = {"outcome": receipt["outcome"],
                                              "receipt": str(path.relative_to(repo))}
    (layer / "results.json").write_text(json.dumps(dict(sorted(results.items(), key=lambda kv: int(kv[0]))),
                                                   indent=2) + "\n")
    print(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
