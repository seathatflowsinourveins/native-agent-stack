#!/usr/bin/env bash
# Measurement distribution only, no model: A2's decision statistic from the four scored runs' validity files, the
# check that both arms ran the same case ids on each surface, and what the invalid cases were (reasons, counted).
set -u
A="$HOME/measure/a2"; L="$A/logs"
for lab in s2o-chat c-chat s2o-responses c-responses; do printf '%s %s\n' "$(sha256sum "$L/$lab/validity.jsonl" | cut -c1-64)" "$lab/validity.jsonl"; done
"$A/venv/bin/python" -B "$A/harness/a2_bootstrap.py" S2o C "chat=$L/s2o-chat/validity.jsonl,$L/c-chat/validity.jsonl" "responses=$L/s2o-responses/validity.jsonl,$L/c-responses/validity.jsonl"; echo "bootstrap exit $?"
python3 - "$L" <<'PY'
import collections, json, pathlib, sys
root = pathlib.Path(sys.argv[1])
for lab in ("s2o-chat", "c-chat", "s2o-responses", "c-responses"):
    rows = [json.loads(line) for line in open(root / lab / "validity.jsonl")]
    cases = [r for r in rows if not r.get("summary")]
    reasons = collections.Counter(r["reason"].split(":")[0] for r in cases if not r["valid"])
    both = sum(1 for r in cases if r["valid"] and r["package_score"] in ("C", 1, 1.0, True))
    print(lab, "| invalid reasons:", dict(reasons) or "none", "| valid and also correct by the package:", both, "| ids:", len({r["id"] for r in cases}))
PY
date -u +%Y-%m-%dT%H:%M:%SZ
