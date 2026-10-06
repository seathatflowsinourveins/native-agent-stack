#!/usr/bin/env python3
"""Frozen validator for wave 1's R2b totals-only profile (deviations-20261006-2.json D4.3; stdlib only).

Usage: python3 -I validate_r2b.py <profile.json>
       python3 -I validate_r2b.py --self-test
Prints one JSON line {"result": "pass"|"reject"|"error", "reason": ..., "detail": ...}.
Exit 0 pass; 1 reject with reason "reconciliation" (R2b REJECTED_RECONCILIATION, exit 31) or any other reason (R2b
REJECTED_SCHEMA, exit 32); 2 cannot read or parse the input (R2b ERROR, exit 2).

Schema (frozen): top-level keys exactly schema_version (1), kind ("rnd_wave1_r2b_profile"), source (r2a_arm "A",
results_sha256 and labels_sha256 equal to the pinned E2 outputs), populations (exactly ratio_3: 97 and ratio_2: 261),
dimensions (one object per population with exactly the five dimensions below) and claims ("insufficient_evidence").
Buckets: year "2021".."2025"; price_bucket by the prior close lt_1 / 1_to_5 / 5_to_20 / 20_plus (USD, lower bound
inclusive); dollar_volume_bucket by the prior session's close x volume lt_1m / 1m_to_5m / 5m_to_20m / 20m_plus;
session_timing premarket / regular / after_hours; catalyst_tag labels are the package's category normalized to
^[a-z][a-z0-9_]{0,39}$, at most 40 labels. Every dimension also has "unknown", where a missing or unparseable value is
counted (never dropped or imputed). Counts are non-negative integers and each dimension sums to its population."""
import json
import re
import sys

POP = {"ratio_3": 97, "ratio_2": 261}
SRC = {"r2a_arm": "A", "results_sha256": "406f582c484b67c3e352c2a31a69a8cd8eb76dfb66ec1fc2c3386a707cb7fb26",
       "labels_sha256": "19e276665707e3ec2ba70aad365afaf6d2277240d4619681627ec87dd8993108"}
FIXED = {"year": {"2021", "2022", "2023", "2024", "2025"},
         "price_bucket": {"lt_1", "1_to_5", "5_to_20", "20_plus"},
         "dollar_volume_bucket": {"lt_1m", "1m_to_5m", "5m_to_20m", "20m_plus"},
         "session_timing": {"premarket", "regular", "after_hours"}}
DIMS = set(FIXED) | {"catalyst_tag"}
LABEL = re.compile(r"[a-z][a-z0-9_]{0,39}")


def check(doc):
    """Return (reason, detail) of the first problem, or None."""
    if not isinstance(doc, dict) or set(doc) != {"schema_version", "kind", "source", "populations", "dimensions", "claims"}:
        return "schema", "top-level keys"
    if doc["schema_version"] != 1 or isinstance(doc["schema_version"], bool) or doc["kind"] != "rnd_wave1_r2b_profile":
        return "schema", "schema_version or kind"
    if doc["source"] != SRC:
        return "schema", "source is not Arm A's pinned outputs"
    if doc["claims"] != "insufficient_evidence":
        return "schema", "claims must be insufficient_evidence"
    if doc["populations"] != POP:
        return "reconciliation", "populations differ from ratio_3 97 and ratio_2 261"
    dims = doc["dimensions"]
    if not isinstance(dims, dict) or set(dims) != set(POP):
        return "schema", "dimensions must hold exactly the two populations"
    for pop, total in POP.items():
        d = dims[pop]
        if not isinstance(d, dict) or set(d) != DIMS:
            return "schema", f"{pop}: exactly the five dimensions"
        for name, buckets in d.items():
            if not isinstance(buckets, dict) or "unknown" not in buckets:
                return "schema", f"{pop}.{name}: an unknown bucket is required"
            keys = set(buckets) - {"unknown"}
            if name in FIXED and keys != FIXED[name]:
                return "schema", f"{pop}.{name}: bucket keys differ from the frozen set"
            if name == "catalyst_tag" and (len(keys) > 40 or not all(LABEL.fullmatch(k) for k in keys)):
                return "schema", f"{pop}.catalyst_tag: labels must match {LABEL.pattern}, at most 40"
            if not all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in buckets.values()):
                return "schema", f"{pop}.{name}: counts must be non-negative integers"
            if sum(buckets.values()) != total:
                return "reconciliation", f"{pop}.{name} sums to {sum(buckets.values())}, not {total}"
    return None


def self_test():
    def dim(total):
        out = {k: ({b: 0 for b in v} | {"unknown": total}) for k, v in FIXED.items()}
        out["catalyst_tag"] = {"unknown": total}
        return out
    good = {"schema_version": 1, "kind": "rnd_wave1_r2b_profile", "source": dict(SRC), "populations": dict(POP),
            "dimensions": {p: dim(n) for p, n in POP.items()}, "claims": "insufficient_evidence"}
    cases = [("pass", good, None)]
    bad = json.loads(json.dumps(good)); bad["dimensions"]["ratio_3"]["year"]["2021"] = 1
    cases.append(("sum off by one", bad, "reconciliation"))
    bad = json.loads(json.dumps(good)); bad["dimensions"]["ratio_2"]["catalyst_tag"] = {"FDA": 1, "unknown": 260}
    cases.append(("uppercase label", bad, "schema"))
    bad = json.loads(json.dumps(good)); del bad["dimensions"]["ratio_2"]["session_timing"]["unknown"]
    cases.append(("missing unknown bucket", bad, "schema"))
    bad = json.loads(json.dumps(good)); bad["populations"]["ratio_3"] = 96
    cases.append(("population drift", bad, "reconciliation"))
    bad = json.loads(json.dumps(good)); bad["claims"] = "predictive"
    cases.append(("predictive claim", bad, "schema"))
    fails = [n for n, doc, want in cases if (check(doc) or (None,))[0] != want]
    print(json.dumps({"self_test": "pass" if not fails else "fail", "cases": len(cases), "failed": fails}))
    return 0 if not fails else 1


def main():
    if len(sys.argv) != 2:
        print(json.dumps({"result": "error", "reason": "usage", "detail": "validate_r2b.py <profile.json> | --self-test"})); return 2
    if sys.argv[1] == "--self-test":
        return self_test()
    try:
        with open(sys.argv[1], encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError) as exc:
        print(json.dumps({"result": "error", "reason": "unreadable", "detail": type(exc).__name__})); return 2
    problem = check(doc)
    if problem:
        print(json.dumps({"result": "reject", "reason": problem[0], "detail": problem[1]})); return 1
    print(json.dumps({"result": "pass", "reason": None, "detail": None})); return 0


if __name__ == "__main__":
    sys.exit(main())
