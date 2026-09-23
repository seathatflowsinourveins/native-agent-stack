"""Compare this host's ARB trace2code rerun with the retained Darwin arm64 receipt.
Usage: arb_compare.py REPO ARB_DIR > comparison.json"""
import hashlib
import json
import sys
from pathlib import Path

repo, arb = Path(sys.argv[1]), Path(sys.argv[2])
ret = repo / "blueprints/convergence-practice/arb-trace2code"
receipt = json.loads((ret / "receipt.json").read_text())
paired = {s["sample_id"]: s for s in json.loads((ret / "paired-samples.json").read_text())["samples"]}
out = {"rankers": {}}
TIMING = ("seconds", "elapsed", "wall", "time")
for ranker in ("lexical", "bm25"):
    details = (arb / f"results/{ranker}-details.jsonl").read_bytes()
    local_sha = hashlib.sha256(details).hexdigest()
    darwin_sha = receipt["runs"][ranker]["native_details_sha256"]
    new = json.loads((arb / f"results/{ranker}-summary.json").read_text())
    old = json.loads((ret / f"upstream-{ranker}-summary.json").read_text())
    def flat(d, prefix=""):
        items = {}
        for k, v in d.items():
            if isinstance(v, dict):
                items.update(flat(v, prefix + k + "."))
            else:
                items[prefix + k] = v
        return items
    fn, fo = flat(new), flat(old)
    differing = sorted(k for k in set(fn) | set(fo) if fn.get(k) != fo.get(k))
    rank_mismatch = []
    for line in details.decode().splitlines():
        row = json.loads(line)
        if paired[row["sample_id"]]["gold_ranks"][ranker] != row["gold_ranks"]:
            rank_mismatch.append(row["sample_id"])
    out["rankers"][ranker] = {
        "local_details_sha256": local_sha, "darwin_details_sha256": darwin_sha,
        "details_byte_identical": local_sha == darwin_sha, "evaluated": new.get("evaluated"),
        "summary_fields_compared": len(set(fn) | set(fo)),
        "summary_fields_differing": differing,
        "differing_fields_all_timing": all(any(t in k.lower() for t in TIMING) for k in differing),
        "headline": {k: fn["metrics.overall." + k] for k in ("Recall@5", "Recall@10", "Recall@20", "MRR")},
        "per_sample_gold_rank_mismatches": rank_mismatch, "samples_compared": len(details.decode().splitlines()),
    }
print(json.dumps(out, indent=1))
