#!/usr/bin/env python3
"""Compare regenerated research-evaluation artifacts with the 42 retained private-artifact hashes."""
import hashlib, json, sys
from pathlib import Path

receipt = json.loads(Path("blueprints/us-equities/research-evaluation/receipt.json").read_text())
wave = Path(sys.argv[1])
home = str(Path.home())
CLOCK_FIELDS = {"run-1/freeze.json": ["frozen_utc"], "run-1/results.json": ["freeze_sha256"]}
rows, counts = [], {}
for name, meta in sorted(receipt["private_artifacts"].items()):
    path = wave / name
    row = {"artifact": name, "retained_sha256": meta["sha256"], "retained_bytes": meta["bytes"]}
    if not path.exists():
        row.update(status="not_regenerated")
    else:
        data = path.read_bytes()
        row.update(regenerated_sha256=hashlib.sha256(data).hexdigest(), regenerated_bytes=len(data))
        if row["regenerated_sha256"] == meta["sha256"]:
            row["status"] = "match"
        elif name in CLOCK_FIELDS:
            value = json.loads(data)
            removed = {k: value.pop(k) for k in CLOCK_FIELDS[name]}
            row.update(status="mismatch", normalized_fields_removed=sorted(removed))
        else:
            row["status"] = "mismatch"
            text = data.decode("utf-8", "replace").replace(home, "$HOME")
            row["regenerated_text_excerpt"] = text[:400]
    counts[row["status"]] = counts.get(row["status"], 0) + 1
    rows.append(row)
# Byte-level reconstruction for clock-bearing files: substitute the retained public frozen_utc into the
# regenerated freeze.json, re-serialize with evaluate.py's own write_new format, then feed the resulting
# freeze hash into results.json. Equality with the retained hashes proves every other byte is identical.
def dump(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
fz = json.loads((wave / "run-1/freeze.json").read_text())
fz["frozen_utc"] = receipt["frozen_plan"]["frozen_utc"]
freeze_hash = hashlib.sha256(dump(fz)).hexdigest()
res = json.loads((wave / "run-1/results.json").read_text())
res["freeze_sha256"] = freeze_hash
results_hash = hashlib.sha256(dump(res)).hexdigest()
semantic = {
    "retained_frozen_utc_substituted": receipt["frozen_plan"]["frozen_utc"],
    "reconstructed_freeze_sha256": freeze_hash,
    "reconstructed_freeze_equals_retained": freeze_hash == receipt["private_artifacts"]["run-1/freeze.json"]["sha256"],
    "reconstructed_results_sha256": results_hash,
    "reconstructed_results_equals_retained": results_hash == receipt["private_artifacts"]["run-1/results.json"]["sha256"],
    "results_equal_public_receipt_results": {k: res[k] == receipt["results"][k] for k in receipt["results"] if k != "freeze_sha256"},
    "results_ledger_records": res["ledger_records"], "results_inputs_unchanged": res["inputs_unchanged"],
}
for row in rows:
    if row["artifact"] == "run-1/freeze.json":
        row["reconstructed_equals_retained"] = semantic["reconstructed_freeze_equals_retained"]
    if row["artifact"] == "run-1/results.json":
        row["reconstructed_equals_retained"] = semantic["reconstructed_results_equals_retained"]
print(json.dumps({"counts": counts, "semantic": semantic, "rows": rows}, indent=2))
