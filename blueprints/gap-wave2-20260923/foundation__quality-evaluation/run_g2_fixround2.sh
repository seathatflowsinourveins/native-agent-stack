#!/usr/bin/env bash
# Fix round 2, gap 2: inject a regression into each winner's PROJECT fixture
# (original / mutant / restored) and capture every exit code to a file.
#   Promptfoo  : examples/promptfoo-nemotron-upstream/promptfooconfig.yaml and its
#                assertion target upstream-example.py (executed copy, sha256 c4b48632...).
#   ShellCheck : the manifest command `shellcheck fixtures/example.sh`.
#   Playwright : blueprints/convergence-practice/application-delivery with its
#                frozen browser/ledger.spec.ts, run in a private network namespace.
# Repository files are copied into WORK; nothing in the checkout is modified.
# Usage: run_g2_fixround2.sh REPO_ROOT WORK OUT PINNED_VENV APP_PREFIX CHROME
set -u
ROOT=$1; WORK=$2; OUT=$3; VENV=$4; APPX=$5; CHROME=$6; HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$WORK" "$OUT"
rc() { echo "$2" > "$OUT/$1.exit"; echo "$1 exit=$2"; }
export PROMPTFOO_DISABLE_TELEMETRY=1 PROMPTFOO_CONFIG_DIR="$WORK/promptfoo-config"

# ---- Promptfoo: the project's upstream-retrieval fixture ----
PF="$WORK/pf-upstream"; mkdir -p "$PF"
cp "$ROOT/examples/promptfoo-nemotron-upstream/promptfooconfig.yaml" "$PF/promptfooconfig.yaml"
cp "$ROOT/evidence/artifacts/gap-wave2-20260923/foundation__quality-evaluation/support/fixround/g7-upstream4/upstream-example.py" "$PF/upstream-example.original.py"
python3 - "$PF/upstream-example.original.py" "$PF/upstream-example.mutant.py" <<'EOF'
import sys
src = open(sys.argv[1]).read()
marker = "\ndef embed("
assert src.count(marker) == 1
inject = "\n# injected regression: documents 2 and 3 swapped, so queries 2 and 3 lose their paired document\nDOCUMENTS[2], DOCUMENTS[3] = DOCUMENTS[3], DOCUMENTS[2]\n"
open(sys.argv[2], "w").write(src.replace(marker, inject + marker))
EOF
diff "$PF/upstream-example.original.py" "$PF/upstream-example.mutant.py" > "$OUT/pf-upstream-mutation.diff"; echo "diff exit (1 = mutation applied): $?" >> "$OUT/pf-upstream-mutation.diff"
for phase in original mutant restored; do
  src=original; [ $phase = mutant ] && src=mutant
  cp "$PF/upstream-example.$src.py" "$PF/upstream-example.py"
  echo "$phase $(sha256sum "$PF/upstream-example.py" | cut -d' ' -f1) upstream-example.py $(sha256sum "$PF/promptfooconfig.yaml" | cut -d' ' -f1) promptfooconfig.yaml" >> "$OUT/pf-upstream-phase.sha256"
  ( cd "$PF" && PATH="$VENV/bin:$PATH" promptfoo eval -c promptfooconfig.yaml --no-cache -j 1 -o "$PF/results-$phase.json" ) > "$OUT/pf-upstream-$phase.stdout" 2> "$OUT/pf-upstream-$phase.stderr"
  rc pf-upstream-$phase $?
  cp "$PF/results-$phase.json" "$OUT/pf-upstream-results-$phase.json"
done

# ---- ShellCheck: the manifest command on the project's fixture ----
SH="$WORK/sh"; mkdir -p "$SH/fixtures"
cp "$ROOT/fixtures/example.sh" "$SH/example.original.sh"
sed 's/printf "%s\\n" "native stack fixture"/printf "%s\\n" $1/' "$SH/example.original.sh" > "$SH/example.mutant.sh"
diff "$SH/example.original.sh" "$SH/example.mutant.sh" > "$OUT/sh-mutation.diff"; echo "diff exit (1 = mutation applied): $?" >> "$OUT/sh-mutation.diff"
for phase in original mutant restored; do
  src=original; [ $phase = mutant ] && src=mutant
  cp "$SH/example.$src.sh" "$SH/fixtures/example.sh"
  echo "$phase $(sha256sum "$SH/fixtures/example.sh" | cut -d' ' -f1) fixtures/example.sh" >> "$OUT/sh-phase.sha256"
  ( cd "$SH" && shellcheck fixtures/example.sh ) > "$OUT/sh-$phase.stdout" 2> "$OUT/sh-$phase.stderr"
  rc sh-$phase $?
done

# ---- Playwright: the project's application, in a private network namespace ----
# Host 127.0.0.1:18080 is held by a running service, so the app, PostgreSQL and
# Chromium run in a new user+network namespace with their own loopback; the inner
# namespace maps the caller's uid back to itself so PostgreSQL does not run as root.
APP="$APPX/application-delivery"
cp "$APP/backend/app.py" "$WORK/app.original.py"
python3 - "$WORK/app.original.py" "$WORK/app.mutant.py" <<'EOF'
import sys
src = open(sys.argv[1]).read()
target = ('        conn.execute("INSERT INTO run_events(run_id,revision,status) VALUES (%s,%s,%s)",\n'
          '                     (run_id, row["revision"], body.status.value))\n')
assert src.count(target) == 1
open(sys.argv[2], "w").write(src.replace(target, "        # injected regression: the update no longer records a history event\n"))
EOF
diff "$WORK/app.original.py" "$WORK/app.mutant.py" > "$OUT/app-mutation.diff"; echo "diff exit (1 = mutation applied): $?" >> "$OUT/app-mutation.diff"
ss -ltn | grep -E ':(15432|18080|18081) ' > "$OUT/app-host-ports-before.txt"
export PATH="$APPX/../bin:$APPX/../sysroot/usr/bin:$PATH" COREPACK_HOME="$APPX/../corepack" COREPACK_ENABLE_NETWORK=0 NEXT_TELEMETRY_DISABLED=1 \
  UV_OFFLINE=1 UV_CACHE_DIR="$APPX/application-delivery/.runtime/uv-cache" UV_PYTHON="$(command -v python3.13)" UV_PYTHON_DOWNLOADS=never XDG_CACHE_HOME="$APPX/../xdg"
unshare -rn bash -c 'ip link set lo up && exec unshare --user --map-user='"$(id -u)"' --map-group='"$(id -g)"' bash "$1" "$2" "$3" "$4" "$5"' _ \
  "$HERE/run_g2_app_inner.sh" "$APPX" "$WORK" "$OUT" "$CHROME" > "$OUT/app-namespace.stdout" 2> "$OUT/app-namespace.stderr"
echo "namespace exit=$?" >> "$OUT/app-namespace.stdout"
cp "$WORK/app.original.py" "$APP/backend/app.py"
ss -ltn | grep -E ':(15432|18081) ' > "$OUT/app-host-ports-after.txt"; echo "host listeners on 15432/18081 after: $(wc -l < "$OUT/app-host-ports-after.txt")" >> "$OUT/app-host-ports-after.txt"
