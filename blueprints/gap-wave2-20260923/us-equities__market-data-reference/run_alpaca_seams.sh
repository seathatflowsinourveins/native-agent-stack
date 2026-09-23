#!/usr/bin/env bash
# Gap 4: run tests/test_alpaca_historical.py unchanged, then against a temp copy whose
# 0.44.0 pin is replaced by the installed version (repository files are never edited).
set -uo pipefail
WT=${WT:-$(cd "$(dirname "$0")/../../.." && pwd)}
PY=$1
cd "$WT"
echo "## seam probe"; "$PY" blueprints/gap-wave2-20260923/us-equities__market-data-reference/seam_probe.py
echo "## unchanged suite"; "$PY" -m unittest tests.test_alpaca_historical -v 2>&1 | tail -n 40; echo "unchanged_exit=${PIPESTATUS[0]}"
V=$("$PY" -c 'import importlib.metadata as m;print(m.version("alpaca-py"))')
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/tests" "$T/blueprints/us-equities/alpaca-historical"
cp tests/test_alpaca_historical.py "$T/tests/"
cp blueprints/us-equities/alpaca-historical/plan.json blueprints/us-equities/alpaca-historical/collect.py "$T/blueprints/us-equities/alpaca-historical/"
sed -i "s/\"0\.44\.0\"/\"$V\"/g" "$T/blueprints/us-equities/alpaca-historical/collect.py" "$T/blueprints/us-equities/alpaca-historical/plan.json"
echo "## pin-lifted copy (pin -> $V); lines changed:"; diff <(cat blueprints/us-equities/alpaca-historical/collect.py blueprints/us-equities/alpaca-historical/plan.json) <(cat "$T"/blueprints/us-equities/alpaca-historical/collect.py "$T"/blueprints/us-equities/alpaca-historical/plan.json) | grep '^[<>]' | sed "s#$T#\$TMP#g"
cd "$T" && "$PY" -m unittest tests.test_alpaca_historical -v 2>&1 | tail -n 40; echo "pin_lifted_exit=${PIPESTATUS[0]}"
