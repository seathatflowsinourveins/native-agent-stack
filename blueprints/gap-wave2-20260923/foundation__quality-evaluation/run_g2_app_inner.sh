#!/usr/bin/env bash
# Runs inside the private user+network namespace created by run_g2_fixround2.sh.
# Starts the owned PostgreSQL on the namespace loopback, migrates, then runs the
# frozen browser oracle against original / mutant / restored backend/app.py.
# Usage: run_g2_app_inner.sh APP_PREFIX WORK OUT CHROME
set -u
APPX=$1; WORK=$2; OUT=$3; export WSL_CHROME_EXECUTABLE=$4
APP="$APPX/application-delivery"; cd "$APP"
rc() { echo "$2" > "$OUT/$1.exit"; echo "$1 exit=$2"; }
echo "namespace uid=$(id -u) gid=$(id -g)"; ip -brief addr > "$OUT/app-ns-interfaces.txt"; ss -ltn > "$OUT/app-ns-listeners-before.txt"
[ -e .runtime/native-pgdata ] || { make postgres-init > "$OUT/app-pg-init.log" 2>&1; rc app-pg-init $?; }
make postgres-start > "$OUT/app-pg-start.log" 2>&1; rc app-pg-start $?
[ -e .runtime/databases-created ] || { make postgres-databases > "$OUT/app-pg-databases.log" 2>&1; rc app-pg-databases $?; touch .runtime/databases-created; }
make migrate > "$OUT/app-migrate.log" 2>&1; rc app-migrate $?
for phase in original mutant restored; do
  src=original; [ $phase = mutant ] && src=mutant
  cp "$WORK/app.$src.py" backend/app.py
  ( sha256sum backend/app.py browser/ledger.spec.ts playwright.config.ts ../wsl-application/playwright.config.ts ) | sed "s/^/$phase /" >> "$OUT/app-phase.sha256"
  taskset -c 0-3 pnpm exec playwright test --config ../wsl-application/playwright.config.ts > "$OUT/app-$phase.stdout" 2> "$OUT/app-$phase.stderr"
  rc app-$phase $?
  cp .runtime/browser-results.json "$OUT/app-$phase-browser-results.json" 2>/dev/null
done
ss -ltn > "$OUT/app-ns-listeners-during.txt"
make postgres-stop > "$OUT/app-pg-stop.log" 2>&1; rc app-pg-stop $?
ss -ltn > "$OUT/app-ns-listeners-after.txt"
