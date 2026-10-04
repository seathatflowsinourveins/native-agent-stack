#!/usr/bin/env bash
# Attempt 2 of the betterleaks 1.8.1 full-history git-mode scan (attempt 1, under the host gitleaks
# guard's 4G/6G/600 s caps, was stopped at 602.7 s with rc=143 and is preserved in logs/scans.tsv).
# Same argument vector as attempt 1 and as validate.yml's secret-scan history step; only the
# containment caps are raised so the scan can complete and its peak memory can be measured.
# The scanner runs with HOME and XDG_CACHE_HOME in this directory (betterleaks's wazero compilation
# cache); that isolation was added in the repair round, after the recorded run (run-record.json, deviations).
set -uo pipefail
D="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
W="$1"; RUNNER="$2"
export ECOSYSTEM_JOB_MEMORY_HIGH=28G ECOSYSTEM_JOB_MEMORY_MAX=32G ECOSYSTEM_JOB_SWAP_MAX=0 \
       ECOSYSTEM_JOB_SECONDS=3600 ECOSYSTEM_JOB_TASKS_MAX=256
unset ECOSYSTEM_JOB_CPU_QUOTA
mkdir -p "$D/iso-home" "$D/iso-cache"
cd "$W" || exit 1
report="$D/reports/betterleaks-git-attempt2.json"; rm -f "$report"
args=(git . --config .gitleaks.toml --max-target-megabytes 2 --log-opts=HEAD --redact --no-banner
      --report-format json --report-path "$report")
start=$(date -u +%Y-%m-%dT%H:%M:%SZ); s=$(date +%s.%N)
"$RUNNER" env HOME="$D/iso-home" XDG_CACHE_HOME="$D/iso-cache" \
  /usr/bin/time -v -o "$D/logs/betterleaks-git-attempt2.time" "$D/betterleaks/betterleaks" "${args[@]}" \
  > "$D/logs/betterleaks-git-attempt2.out" 2> "$D/logs/betterleaks-git-attempt2.err"
rc=$?; e=$(date +%s.%N)
printf '%s\t%s\tstart=%s\telapsed_s=%.1f\trc=%s\tcaps=28G/32G/3600s\targv=betterleaks %s\n' betterleaks git-attempt2 \
  "$start" "$(echo "$e - $s" | bc)" "$rc" "${args[*]//$D/<scratch>}" >> "$D/logs/scans.tsv"
