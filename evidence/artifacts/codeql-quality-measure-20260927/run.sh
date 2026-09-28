#!/usr/bin/env bash
# Local integration glue (not a tool): runs only upstream CodeQL CLI 2.27.1
# commands from the verified codeql-bundle-v2.27.1 (github/codeql-action release).
# Commands follow GitHub's CLI docs: "codeql database create" and
# "codeql database analyze" (docs.github.com/en/code-security/codeql-cli).
# Every step logs its argv, UTC start/end and exit code to steps.tsv.
# A failed step stops its language pipeline. The script waits on each
# pipeline's PID, because a bare `wait` returns zero whatever the jobs returned
# (bash(1), SHELL BUILTIN COMMANDS, wait). It ends steps.tsv with ALL DONE and
# exits 0 only when every pipeline succeeded; otherwise it appends a FAILED
# line naming the failed pipelines and exits 1.
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
      --sarif-category="/language:$lang" --threads="$THREADS" --ram="$RAM" || return 1
  done
}

pids=() langs=()
lang_pipeline python python-queries python --build-mode=none &
pids+=("$!"); langs+=(python)
lang_pipeline javascript javascript-queries javascript --build-mode=none &
pids+=("$!"); langs+=(javascript)
lang_pipeline actions actions-queries actions &
pids+=("$!"); langs+=(actions)

failed=""
for i in "${!pids[@]}"; do
  wait "${pids[$i]}" || failed="$failed ${langs[$i]}"
done
if [ -n "$failed" ]; then
  echo "FAILED $(date -u +%FT%TZ)$failed" >> "$DL/steps.tsv"
  exit 1
fi
echo "ALL DONE $(date -u +%FT%TZ)" >> "$DL/steps.tsv"
