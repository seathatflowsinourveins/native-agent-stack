#!/usr/bin/env bash
# Gap 1 (full upstream todomvc suite), gap 2 (mutation catch for three winners:
# original / mutant / restored) and gap 3 (shellcheck + difftastic content
# assertions). Every exit code is written to a file under $OUT.
# Usage: run_g1_g2_g3.sh WORKDIR OUT
set -u
WORK=$1; OUT=$2; HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$OUT"
REPO=$HOME/.cache/gap-wave2-20260923/quality-evaluation/playwright-upstream/repo/examples/todomvc
export PLAYWRIGHT_BROWSERS_PATH=$HOME/.cache/gap-wave2-20260923/web-research/ms-playwright PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
export PROMPTFOO_DISABLE_TELEMETRY=1 PROMPTFOO_CONFIG_DIR="$WORK/promptfoo-config"
rc() { echo "$2" > "$OUT/$1.exit"; echo "$1 exit=$2"; }

# ---- Gap 1: whole upstream examples/todomvc suite against the real app ----
( cd "$REPO" && npx playwright test --project=chromium --reporter=list ) > "$OUT/g1-full-suite.stdout" 2> "$OUT/g1-full-suite.stderr"
rc g1-full-suite $?

# ---- Gap 2 / Promptfoo: original, mutant, restored provider ----
PF="$WORK/pf"; mkdir -p "$PF"
cat > "$PF/promptfooconfig.yaml" <<'EOF'
description: Mutation-catch check for Promptfoo winner
prompts: ["hello"]
providers:
  - id: exec:python3 echo_provider.py
tests:
  - assert:
      - type: equals
        value: "EXPECTED_OUTPUT_42"
EOF
printf 'print("EXPECTED_OUTPUT_42")\n' > "$PF/echo_provider.original.py"
printf 'print("MUTATED_WRONG_OUTPUT")\n' > "$PF/echo_provider.mutant.py"
for phase in original mutant restored; do
  src=original; [ $phase = mutant ] && src=mutant
  cp "$PF/echo_provider.$src.py" "$PF/echo_provider.py"
  cp "$PF/echo_provider.py" "$OUT/g2-promptfoo-provider.$phase.py"
  ( cd "$PF" && promptfoo eval -c promptfooconfig.yaml --no-cache -j 1 ) > "$OUT/g2-promptfoo-$phase.stdout" 2> "$OUT/g2-promptfoo-$phase.stderr"
  rc g2-promptfoo-$phase $?
done
cp "$PF/promptfooconfig.yaml" "$OUT/g2-promptfoo-config.yaml"

# ---- Gap 2 / Playwright: mutate the APPLICATION served from a loopback TLS mirror ----
MIR="$WORK/todomvc-mirror"; PORT=18443
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=demo.playwright.dev \
  -keyout "$WORK/mirror.key" -out "$WORK/mirror.crt" 2>/dev/null
cp "$MIR/js/bundle.js" "$WORK/bundle.original.js"
sed 's/return count === 1 ? word : word + '"'"'s'"'"';/return count === 0 ? word : word + '"'"'s'"'"';/' \
  "$WORK/bundle.original.js" > "$WORK/bundle.mutant.js"
diff "$WORK/bundle.original.js" "$WORK/bundle.mutant.js" > "$OUT/g2-playwright-app-mutation.diff"
echo "diff exit (1 = mutation applied): $?" >> "$OUT/g2-playwright-app-mutation.diff"
cp "$HERE/local-mirror.config.ts" "$REPO/local-mirror.config.ts"
SPEC=tests/todo-creation/add-single-todo.spec.ts
: > "$OUT/g2-playwright-spec.sha256"
python3 "$HERE/serve_mirror.py" "$MIR" $PORT "$WORK/mirror.crt" "$WORK/mirror.key" "$OUT/g2-mirror-access.log" &
SRV=$!; sleep 1
for phase in original mutant restored; do
  src=original; [ $phase = mutant ] && src=mutant
  cp "$WORK/bundle.$src.js" "$MIR/js/bundle.js"
  echo "=== phase $phase bundle sha256=$(sha256sum "$MIR/js/bundle.js" | cut -d' ' -f1)" >> "$OUT/g2-mirror-access.log"
  ( cd "$REPO" && sha256sum $SPEC tests/fixtures.ts playwright.config.ts ) | sed "s/^/$phase /" >> "$OUT/g2-playwright-spec.sha256"
  ( cd "$REPO" && MIRROR_PORT=$PORT npx playwright test -c local-mirror.config.ts $SPEC --project=chromium ) > "$OUT/g2-playwright-$phase.stdout" 2> "$OUT/g2-playwright-$phase.stderr"
  rc g2-playwright-$phase $?
done
kill $SRV; wait $SRV 2>/dev/null
rm -f "$REPO/local-mirror.config.ts"
curl -sk -m 3 -o /dev/null -w '%{http_code}\n' https://127.0.0.1:$PORT/todomvc/ > "$OUT/g2-mirror-after-stop.txt" 2>&1; echo "curl exit=$?" >> "$OUT/g2-mirror-after-stop.txt"

# ---- Gap 2 / Shell: clean original, mutant (unquoted expansion), restored ----
SH="$WORK/sh"; mkdir -p "$SH"
printf '#!/bin/bash\nFILES=$1\nfor f in $FILES; do\n  echo "$f"\ndone\n' > "$SH/loop.original.sh"
sed 's/echo "\$f"/echo $f/' "$SH/loop.original.sh" > "$SH/loop.mutant.sh"
for phase in original mutant restored; do
  src=original; [ $phase = mutant ] && src=mutant
  cp "$SH/loop.$src.sh" "$SH/loop.sh"; cp "$SH/loop.sh" "$OUT/g2-shell-loop.$phase.sh"
  ( cd "$SH" && shellcheck -f gcc loop.sh ) > "$OUT/g2-shellcheck-$phase.stdout" 2> "$OUT/g2-shellcheck-$phase.stderr"
  rc g2-shellcheck-$phase $?
done

# ---- Gap 3: shellcheck on warning + clean fixtures; difft content assertions ----
G3="$WORK/g3"; mkdir -p "$G3/a" "$G3/b"
printf '#!/bin/bash\nFILES=$1\nfor f in $FILES; do\n  echo $f\ndone\n' > "$G3/bad.sh"
printf '#!/bin/bash\nFILES=$1\nfor f in $FILES; do\n  echo "$f"\ndone\n' > "$G3/clean.sh"
printf '#!/bin/bash\necho "hello"\necho "world"\n' > "$G3/a/file.sh"
printf '#!/bin/bash\necho "hello"\necho "there"\n' > "$G3/b/file.sh"
cp -r "$G3/a" "$G3/b" "$G3/bad.sh" "$G3/clean.sh" "$OUT/" 2>/dev/null; mv "$OUT/a" "$OUT/g3-a"; mv "$OUT/b" "$OUT/g3-b"; mv "$OUT/bad.sh" "$OUT/g3-bad.sh"; mv "$OUT/clean.sh" "$OUT/g3-clean.sh"
( cd "$G3" && shellcheck -f json bad.sh ) > "$OUT/g3-shellcheck-bad.json" 2> "$OUT/g3-shellcheck-bad.stderr"; rc g3-shellcheck-bad $?
( cd "$G3" && shellcheck -f json clean.sh ) > "$OUT/g3-shellcheck-clean.json" 2> "$OUT/g3-shellcheck-clean.stderr"; rc g3-shellcheck-clean $?
python3 -c "import json,sys; print(sorted({c['code'] for c in json.load(open(sys.argv[1]))}))" "$OUT/g3-shellcheck-bad.json" > "$OUT/g3-shellcheck-bad.codes"
( cd "$G3" && difft --color never --exit-code a/file.sh b/file.sh ) > "$OUT/g3-difft-changed.stdout" 2> "$OUT/g3-difft-changed.stderr"; rc g3-difft-changed $?
( cd "$G3" && difft --color never --exit-code a/file.sh a/file.sh ) > "$OUT/g3-difft-identical.stdout" 2> "$OUT/g3-difft-identical.stderr"; rc g3-difft-identical $?
# Content assertions: the changed token must appear in the changed-file output and not in the identical-file output.
grep -q 'there' "$OUT/g3-difft-changed.stdout"; rc g3-assert-changed-token-present $?
grep -q 'there' "$OUT/g3-difft-identical.stdout"; rc g3-assert-changed-token-absent-on-identical $?
shellcheck --version | sed -n 2p > "$OUT/versions.txt"; difft --version | head -1 >> "$OUT/versions.txt"; promptfoo --version 2>/dev/null >> "$OUT/versions.txt"
( cd "$REPO" && npx playwright --version ) >> "$OUT/versions.txt" 2>/dev/null
