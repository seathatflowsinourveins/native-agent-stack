#!/usr/bin/env bash
# S2 sequencer: 3 tasks x 4 arms x 2 attempts, arm order reversed on attempt 2. It only orders run_task.py calls.
#   run_s2.sh KIT_DIR STATE_A STATE_B LOG
# STATE_A is a staged state dir (stage.py with the default lane: no compression header on the stack arms); STATE_B is a second
# state dir staged with --stack-compression off whose runs/ is a symlink to STATE_A/runs, so both write one runs/ directory.
# The four arms: plain (header off), stack and stack-ext from STATE_A (default lane), stack-gwoff (the stack arm of STATE_B).
# Before each attempt it refreshes the pool with upstream's manual refresh (POST /api/usage/provider-limits, cache only) and stops
# below 30 points; before each run it waits while the host load is 30 or more. A file named <this script>.STOP ends it early.
set -u
K=$1; A=$2; B=$3; LOG=$4
export PYTHONDONTWRITEBYTECODE=1
RUNS=0; FAILED=0
pool_left() { python3 - <<'PY'
import json, urllib.request
try:
    d = json.load(urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:20128/api/usage/provider-limits', data=b'', method='POST'), timeout=90))
    print(max((((v.get('quotas') or {}).get('session') or {}).get('remaining') or 0) for v in d['caches'].values()))
except Exception:
    print(-1)
PY
}
run_one() { # label state arm task attempt
  local label=$1 state=$2 arm=$3 task=$4 att=$5
  if [ "$(cut -d' ' -f1 /proc/loadavg | cut -d. -f1)" -ge 30 ]; then echo "host load >= 30, waiting" >> "$LOG"; while [ "$(cut -d' ' -f1 /proc/loadavg | cut -d. -f1)" -ge 30 ]; do sleep 20; done; fi
  ( cd "$K" && python3 run_task.py --state "$state" --arm "$arm" --task "$task" --attempt "$att" --tag s2 ) >> "$LOG" 2>&1
  rc=$?
  RUNS=$((RUNS + 1)); [ $rc -eq 0 ] || FAILED=$((FAILED + 1))
  echo "== $label $task a$att exit $rc" >> "$LOG"
}
for att in 1 2; do
  left=$(pool_left); echo "-- attempt $att, pool left $left at $(date -u +%H:%M:%SZ)" >> "$LOG"
  if [ "$left" != "-1" ] && [ "$left" -lt 30 ]; then echo "pool below 30, stopping" >> "$LOG"; break; fi
  for task in calc-sign-bug log-triage multi-file-rename; do
    [ -e "$0.STOP" ] && { echo "STOP file, ending" >> "$LOG"; break 2; }
    if [ $att -eq 1 ]; then order="plain stack stack-gwoff stack-ext"; else order="stack-ext stack-gwoff stack plain"; fi
    for l in $order; do
      case $l in
        stack-gwoff) run_one $l "$B" stack "$task" $att ;;
        *)           run_one $l "$A" $l "$task" $att ;;
      esac
    done
  done
done
echo "S2 DONE runs=$RUNS expected=24 failed_runs=$FAILED" >> "$LOG"
[ "$RUNS" -eq 24 ] && [ "$FAILED" -eq 0 ]
