#!/usr/bin/env bash
# Negative control for gap 4: remove `client._retry = 0` in a temp copy and show the
# single-attempt test detects native retries on the given SDK.
set -uo pipefail
WT=${WT:-$(cd "$(dirname "$0")/../../.." && pwd)}; PY=$1; cd "$WT"
V=$("$PY" -c 'import importlib.metadata as m;print(m.version("alpaca-py"))')
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/tests" "$T/blueprints/us-equities/alpaca-historical"
cp tests/test_alpaca_historical.py "$T/tests/"; cp blueprints/us-equities/alpaca-historical/{plan.json,collect.py} "$T/blueprints/us-equities/alpaca-historical/"
sed -i "s/\"0\.44\.0\"/\"$V\"/g" "$T"/blueprints/us-equities/alpaca-historical/{collect.py,plan.json}
sed -i '/client\._retry = 0/d' "$T/blueprints/us-equities/alpaca-historical/collect.py"
grep -c '_retry = 0' "$T/blueprints/us-equities/alpaca-historical/collect.py"
cd "$T" && timeout 300 "$PY" -m unittest tests.test_alpaca_historical.AlpacaHistoricalTests.test_native_get_retains_exact_bytes_and_disables_redirect_retry 2>&1 | grep -vi deprecat | tail -n 8; echo "mutant_exit=${PIPESTATUS[0]}"
