#!/bin/sh
# Scan, check and run one frozen mover paper trial. Usage: run-trial.sh TRIAL_ID CONFIG RULE
set -u
T="${T:?set T to the private trial workspace}"
PY="$T/engine/bin/python"
ENV_FILE="$HOME/.config/native-agent-stack/alpaca-paper.env"
SRC="$T/src/blueprints/us-equities"
TRIAL="$1"; CONFIG="$2"; RULE="$3"
OUT="$T/$TRIAL"
mkdir -p "$OUT/pages" "$OUT/live"
chmod 700 "$OUT" "$OUT/pages"

echo "scan start $(TZ=America/New_York date '+%H:%M:%S') ET"
"$PY" "$SRC/mover-early-entry/mover_scan.py" --env-file "$ENV_FILE" --rule "$RULE" \
    --out "$OUT/scan-full.json" --pages "$OUT/pages" --engine-out "$OUT/scan.json" > "$OUT/scan.log" 2>&1
rc=$?
echo "scan rc=$rc end $(TZ=America/New_York date '+%H:%M:%S') ET"
tail -3 "$OUT/scan.log"
[ "$rc" -eq 0 ] || exit 2

cd "$SRC/adaptive-paper" || exit 2
"$PY" mover_runner.py check --config "$CONFIG" --scan "$OUT/scan.json" --output "$OUT/check.json" > "$OUT/check.log" 2>&1
rc=$?
echo "check rc=$rc"
[ "$rc" -eq 0 ] || { tail -5 "$OUT/check.log"; exit 2; }

echo "paper start $(TZ=America/New_York date '+%H:%M:%S') ET"
"$PY" mover_runner.py paper --env-file "$ENV_FILE" --config "$CONFIG" --scan "$OUT/scan.json" \
    --trial "$TRIAL" --output "$OUT/mover-paper.json" --live-dir "$OUT/live" --allow-shared-account \
    > "$OUT/paper.log" 2>&1
rc=$?
echo "paper rc=$rc end $(TZ=America/New_York date '+%H:%M:%S') ET"
tail -3 "$OUT/paper.log"
exit "$rc"
