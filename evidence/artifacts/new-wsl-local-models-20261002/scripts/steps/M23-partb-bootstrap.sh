#!/usr/bin/env bash
# Part B decision statistic on records alone (amendment 4, rule order): first E1 against E2 (higher minus lower by
# the reported nDCG@10), then E3, which passed gate F, against that single-server winner. E4 ran out of memory in its
# full run (amendment 4a item 8) and has no predictions. Loads no model.
set -u
cd "$HOME/measure/partb/harness" || exit 1
echo "start $(date -u +%Y-%m-%dT%H:%M:%SZ) bootstrap sha256 $(sha256sum partb_bootstrap.py | cut -c1-64)"
for run in E1-pb1 E2-pb1 E3-pb2 E4-pb2; do
  printf '%s summary: ' "$run"; cat "../runs/$run/per-query-summary.json" 2>/dev/null || echo "none"; echo
done
echo "== E1 minus E2"; ../venv/bin/python -B partb_bootstrap.py --challenger ../runs/E1-pb1 --baseline ../runs/E2-pb1; echo "exit $?"
echo "== E3 minus E1"; ../venv/bin/python -B partb_bootstrap.py --challenger ../runs/E3-pb2 --baseline ../runs/E1-pb1; echo "exit $?"
echo "== E3 minus E2 (recorded, not deciding)"; ../venv/bin/python -B partb_bootstrap.py --challenger ../runs/E3-pb2 --baseline ../runs/E2-pb1; echo "exit $?"
echo "end $(date -u +%Y-%m-%dT%H:%M:%SZ)"
