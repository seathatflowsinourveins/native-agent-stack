"""Generate results.json and the README outcome table from the receipts (never by hand)."""
import glob, json, os, re

D = "evidence/artifacts/gap-wave2-20260923/foundation__durable-memory"
rows = {}
for p in glob.glob(os.path.join(D, "*.json")):
    base = os.path.basename(p)
    if not re.match(r"^\d+-", base):
        continue
    r = json.load(open(p))
    assert base.startswith(f"{r['gap_index']}-"), base
    rows[r["gap_index"]] = {"outcome": r["outcome"], "receipt": p}
lines = ["{"]
keys = sorted(rows)
for i, k in enumerate(keys):
    sep = "," if i < len(keys) - 1 else ""
    lines.append(f'  "{k}": {{"outcome": "{rows[k]["outcome"]}", "receipt": "{rows[k]["receipt"]}"}}{sep}')
lines.append("}")
open(os.path.join(D, "results.json"), "w").write("\n".join(lines) + "\n")
assert {int(k): v for k, v in json.load(open(os.path.join(D, "results.json"))).items()} == rows

readme = os.path.join(D, "README.md")
text = open(readme).read()
table = ["| gap | outcome | evidence_class | receipt |", "|---|---|---|---|"]
for k in keys:
    r = json.load(open(rows[k]["receipt"]))
    table.append(f"| {k} | {r['outcome']} | {r['evidence_class']} | `{os.path.basename(rows[k]['receipt'])}` |")
start, end = "<!-- outcome-table:start (generated from receipts by gen_results.py) -->", "<!-- outcome-table:end -->"
text = re.sub(re.escape(start) + r".*?" + re.escape(end), start + "\n" + "\n".join(table) + "\n" + end, text, flags=re.S)
open(readme, "w").write(text)
print(json.dumps({k: rows[k]["outcome"] for k in keys}))
