#!/usr/bin/env bash
# Repair-round scans (local integration; not upstream tests), run from the scratch directory that holds
# the verified betterleaks 1.8.1 binary, inside ecosystem-bounded-run with the raised caps of
# run_bl_git2.sh. The scanner gets HOME and XDG_CACHE_HOME in this directory. Every run uses the trial
# job's final flags (--max-archive-depth 0 and an explicit --gitleaks-ignore-path) and --redact.
#   G1, T1: --gitleaks-ignore-path .gitleaksignore, the job's argument vectors. G1 scans the recorded
#           commit set (--log-opts=<base commit>); T1 scans the worktree.
#   G2, T2: a scratch ignore file holding one fingerprint from the recorded report
#           (prepare_ignore_controls.py).
#   G3, T3: an empty directory as --gitleaks-ignore-path.
# betterleaks also reads the scanned directory's own ignore file (cmd/root.go lines 465-469), so the
# repository's .gitleaksignore is loaded in every run. Reports stay here.
set -uo pipefail
D="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
W="$1"; RUNNER="$2"; BASE="$3"
export ECOSYSTEM_JOB_MEMORY_HIGH=28G ECOSYSTEM_JOB_MEMORY_MAX=32G ECOSYSTEM_JOB_SWAP_MAX=0 \
       ECOSYSTEM_JOB_SECONDS=3600 ECOSYSTEM_JOB_TASKS_MAX=256
unset ECOSYSTEM_JOB_CPU_QUOTA
mkdir -p "$D/iso-home" "$D/iso-cache" "$D/repair/empty"
cd "$W" || exit 1

scan() {  # label, ignore path, source arguments...
  local label="$1" ignore="$2"; shift 2
  local report="$D/repair/$label.json" start s e rc n
  rm -f "$report"
  start=$(date -u +%Y-%m-%dT%H:%M:%SZ); s=$(date +%s.%N)
  "$RUNNER" env HOME="$D/iso-home" XDG_CACHE_HOME="$D/iso-cache" "$D/betterleaks/betterleaks" "$@" \
    --config .gitleaks.toml --max-target-megabytes 2 --max-archive-depth 0 --gitleaks-ignore-path "$ignore" \
    --redact --no-banner --report-format json --report-path "$report" \
    > "$D/repair/$label.out" 2> "$D/repair/$label.err"
  rc=$?; e=$(date +%s.%N)
  n=$(jq '(. // []) | length' "$report" 2>/dev/null || echo no-report)
  printf '%s\tstart=%s\telapsed_s=%.1f\trc=%s\tfindings=%s\tlog=%s\n' "$label" "$start" "$(echo "$e - $s" | bc)" \
    "$rc" "$n" "$(sed 's/\x1b\[[0-9;]*m//g' "$D/repair/$label.err" | tail -n 2 | tr '\n' ' ')" | tee -a "$D/repair/scans.tsv"
}

scan G1-job-argv .gitleaksignore git . --log-opts="$BASE"
scan G2-one-fingerprint "$D/repair/ignore-git.txt" git . --log-opts="$BASE"
scan G3-empty-dir "$D/repair/empty" git . --log-opts="$BASE"
scan T1-job-argv .gitleaksignore dir .
scan T2-one-fingerprint "$D/repair/ignore-dir.txt" dir .
scan T3-empty-dir "$D/repair/empty" dir .
