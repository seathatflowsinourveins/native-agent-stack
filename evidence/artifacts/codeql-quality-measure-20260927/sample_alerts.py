#!/usr/bin/env python3
"""Draw the stratified 20-alert triage sample and a gate-relevant supplement.

Evidence class: local integration (thin glue).

Main sample (the brief's 20 code-quality alerts). Strata are (language,
rule). Quotas: python 16, javascript-typescript 4, actions 0 (its
code-quality suite selects no queries at CodeQL 2.27.1). Within a language
every error-level rule is taken first (these interact with the ruleset's
alerts_threshold: errors), then the remaining rules by descending result
count (ties by rule id) until the quota is met. One alert per selected rule
is drawn with random.Random(SEED) from that rule's results sorted by
(uri, line, column), so the draw is reproducible from the SARIF alone.

Supplement (labelled separately): rules that only security-and-quality adds
and that the current ruleset thresholds act on (error level, or security
severity high or higher): fixed per-rule counts drawn with
random.Random(SEED + ":supplement") the same way.

Usage: sample_alerts.py SARIF_DIR OUT_JSON
"""
import collections
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import summarize_sarif as s  # noqa: E402

SEED = "codeql-quality-measure-20260927"
QUOTAS = {"python": 16, "javascript": 4, "actions": 0}
SUPPLEMENT = {
    "python": {"py/uninitialized-local-variable": 2, "py/overly-permissive-file": 2, "py/partial-ssrf": 1},
    "javascript": {"js/file-system-race": 1},
}


def row(lang, rule, pool, pick):
    return {
        "language": s.LANGS[lang], "rule": rule, "level": pick["level"], "kind": s.kind(pick),
        "precision": pick["precision"], "security_severity": pick["security_severity"],
        "rule_results": len(pool), "uri": pick["uri"], "line": pick["line"], "column": pick["column"],
        "lane": pick["lane"], "message": pick["message"], "related": pick["related"],
    }


def by_rule(path):
    groups = collections.defaultdict(list)
    for r in s.load(path)["results"]:
        groups[r["rule"]].append(r)
    for rule in groups:
        groups[rule].sort(key=lambda r: (r["uri"], r["line"] or 0, r["column"] or 0))
    return groups


def main():
    sarif_dir, out = Path(sys.argv[1]), Path(sys.argv[2])
    rng = random.Random(SEED)
    sample = []
    for lang, quota in QUOTAS.items():
        groups = by_rule(sarif_dir / f"{lang}-code-quality.sarif")
        errors = sorted(k for k, v in groups.items() if v[0]["level"] == "error")
        rest = sorted((k for k in groups if k not in errors), key=lambda k: (-len(groups[k]), k))
        for rule in (errors + rest)[:quota]:
            pool = groups[rule]
            sample.append(row(lang, rule, pool, pool[rng.randrange(len(pool))]))
    srng = random.Random(SEED + ":supplement")
    supplement = []
    for lang, rules in SUPPLEMENT.items():
        groups = by_rule(sarif_dir / f"{lang}-security-and-quality.sarif")
        for rule, count in rules.items():
            pool = groups[rule]
            for index in sorted(srng.sample(range(len(pool)), min(count, len(pool)))):
                supplement.append(row(lang, rule, pool, pool[index]))
    out.write_text(json.dumps({"seed": SEED, "quotas": QUOTAS, "supplement_counts": SUPPLEMENT,
                               "sample": sample, "supplement": supplement}, indent=1) + "\n", encoding="utf-8")
    for label, rows in (("S", sample), ("X", supplement)):
        for i, a in enumerate(rows, 1):
            print(f"{label}{i:02d} {a['language']:21s} {a['rule']:40s} {a['level']:7s} n={a['rule_results']:3d} "
                  f"{a['uri']}:{a['line']}:{a['column']} [{a['lane']}] related={a['related'][:3]}")
            print(f"     msg: {a['message'][:170]}")


if __name__ == "__main__":
    main()
