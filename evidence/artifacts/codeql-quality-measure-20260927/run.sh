#!/usr/bin/env bash
# Local integration glue (not a tool): runs only upstream CodeQL CLI 2.27.1
# commands from the verified codeql-bundle-v2.27.1 (github/codeql-action release).
# Commands follow GitHub's CLI docs: "codeql database create" and
# "codeql database analyze" (docs.github.com/en/code-security/codeql-cli).
# Every step logs its argv, UTC start/end and exit code to steps.tsv.
set -u
DL="$(cd "$(dirname "$0")" && pwd)"
CQ="$DL/codeql/codeql"
SRC="$1"                      # the owned worktree at the base commit
THREADS="${THREADS:-8}"
RAM="${RAM:-12288}"
mkdir -p "$DL/db" "$DL/sarif" "$DL/logs"
: > "$DL/steps.tsv"

step() {  # step <label> <argv...>
  local label="$1"; shift
  local start end rc
  start=$(date -u +%FT%TZ)
  "$@" > "$DL/logs/$label.out" 2> "$DL/logs/$label.err"
  rc=$?
  end=$(date -u +%FT%TZ)
  printf '%s\t%s\t%s\t%s\t%s\n' "$label" "$start" "$end" "$rc" "$*" >> "$DL/steps.tsv"
  return $rc
}

lang_pipeline() {  # lang_pipeline <cli-language> <pack> <suite-prefix> <build-mode-args...>
  local lang="$1" pack="$2" prefix="$3"; shift 3
  step "create-$lang" "$CQ" database create "$DL/db/$lang" --language="$lang" "$@" \
    --source-root="$SRC" --threads="$THREADS" --ram="$RAM" --overwrite || return 1
  for suite in code-scanning code-quality security-and-quality; do
    step "analyze-$lang-$suite" "$CQ" database analyze "$DL/db/$lang" \
      "codeql/$pack:codeql-suites/$prefix-$suite.qls" \
      --format=sarif-latest --output="$DL/sarif/$lang-$suite.sarif" \
      --sarif-category="/language:$lang" --threads="$THREADS" --ram="$RAM"
  done
}

lang_pipeline python python-queries python --build-mode=none &
lang_pipeline javascript javascript-queries javascript --build-mode=none &
lang_pipeline actions actions-queries actions &
wait
echo "ALL DONE $(date -u +%FT%TZ)" >> "$DL/steps.tsv"
