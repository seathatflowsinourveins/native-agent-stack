#!/usr/bin/env python3
"""Fix round 2 post-hoc diagnostic (not preregistered): cosine margin between the
correct passage and the best distractor, Nemotron with model-card input types.

Usage: margins_fixround2.py CASES_JSON [CASES_JSON ...]
"""
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from heldout_common import cosine, embed_typed  # noqa: E402

for path in sys.argv[1:]:
    margins = []
    for case in json.load(open(path)):
        qv, _ = embed_typed("query", [case["query"]])
        dv, _ = embed_typed("document", [case["correct"]] + case["distractors"])
        sims = [cosine(qv[0], v) for v in dv]
        margins.append(sims[0] - max(sims[1:]))
    print(json.dumps({"cases": os.path.basename(path), "n": len(margins), "median_margin": round(statistics.median(margins), 4),
                      "min_margin": round(min(margins), 4), "mean_best_distractor_gap": round(statistics.mean(margins), 4),
                      "margins": [round(m, 4) for m in margins]}))
