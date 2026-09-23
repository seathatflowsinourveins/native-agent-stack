#!/usr/bin/env python3
"""Generate results.json (gap_index -> outcome, receipt) from the receipts; never edited by hand."""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
EV = REPO / 'evidence/artifacts/gap-wave2-20260923/foundation__observation-inference'
out = {}
for p in sorted(EV.glob('[0-9]*-*.json'), key=lambda p: int(p.name.split('-')[0])):
    r = json.loads(p.read_text())
    out[str(r['gap_index'])] = {'outcome': r['outcome'], 'receipt': str(p.relative_to(REPO))}
(EV / 'results.json').write_text(json.dumps({'layer': 'foundation/observation-inference', 'generated_by': 'blueprints/gap-wave2-20260923/foundation__observation-inference/make_results.py', 'results': out}, indent=2) + '\n')
print(json.dumps(out, indent=1))
