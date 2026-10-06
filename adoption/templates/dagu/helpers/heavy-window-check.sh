#!/bin/bash
# Dagu precondition for the co-op's corrected 2026-10-06 resource windows.
# Sources: PAPER WINDOWS direction 2026-10-06T05:04:26Z and Dagu 2.18.2
# preconditions schema at 5ca5c59f; source token-report unit's command condition.
# Exit 1 defers a new heavy phase; it never kills a running case.
set -euo pipefail

duration=${1:?usage: heavy-window-check.sh MAX_SECONDS [TEST_EPOCH]}
case "$duration" in ''|*[!0-9]*) echo "invalid duration" >&2; exit 2;; esac
if test "$duration" -gt 86400; then echo "duration out of bound" >&2; exit 2; fi
duration=$((10#$duration))
now=${2:-$(/usr/bin/date -u +%s)}
case "$now" in ''|*[!0-9]*) echo "invalid epoch" >&2; exit 2;; esac
if test "$now" -gt 4102444800; then echo "epoch out of bound" >&2; exit 2; fi
now=$((10#$now))
finish=$((now + duration))
if { test "$now" -lt 1791294300 && test "$finish" -gt 1791282900; } ||
   { test "$now" -lt 1791331800 && test "$finish" -gt 1791316200; }; then
  echo "heavy phase deferred for the 2026-10-06 paper window" >&2
  exit 1
fi
