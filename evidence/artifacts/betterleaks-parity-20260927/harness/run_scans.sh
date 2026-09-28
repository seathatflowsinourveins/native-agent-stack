#!/usr/bin/env bash
# Local integration harness (not an upstream test): runs the pinned, verified gitleaks 8.30.1 and
# betterleaks 1.8.1 binaries with the argument vectors .github/workflows/validate.yml's secret-scan
# job uses (git mode: --log-opts="HEAD"; dir mode), inside the host's ecosystem-bounded-run
# containment with the same caps the host gitleaks guard applies (4G high, 6G max, no swap, 600 s).
# Reports stay in this scratch directory; they are --redact'ed and never copied into the repository.
# The scanners run with HOME and XDG_CACHE_HOME in this directory: betterleaks's regex engine keeps a
# wazero compilation cache under the user cache directory. The recorded runs used this script without
# that isolation and wrote the cache to the real home (run-record.json, deviations); the isolation was
# added in the repair round, and the scans in run_repair_scans.sh ran with it.
set -uo pipefail
D="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
W="$1"                 # worktree to scan (cwd for every scan, source argument ".")
RUNNER="$2"            # ecosystem-bounded-run
export ECOSYSTEM_JOB_MEMORY_HIGH=4G ECOSYSTEM_JOB_MEMORY_MAX=6G ECOSYSTEM_JOB_SWAP_MAX=0 \
       ECOSYSTEM_JOB_SECONDS=600 ECOSYSTEM_JOB_TASKS_MAX=256
unset ECOSYSTEM_JOB_CPU_QUOTA
mkdir -p "$D/iso-home" "$D/iso-cache"
ISO=(env HOME="$D/iso-home" XDG_CACHE_HOME="$D/iso-cache")
cd "$W" || exit 1
for tool in gitleaks betterleaks; do
  bin="$D/$tool/$tool"
  for mode in git dir; do
    report="$D/reports/$tool-$mode.json"; err="$D/logs/$tool-$mode.err"
    rm -f "$report"
    if [ "$mode" = git ]; then
      args=(git . --config .gitleaks.toml --max-target-megabytes 2 --log-opts=HEAD --redact --no-banner
            --report-format json --report-path "$report")
    else
      args=(dir . --config .gitleaks.toml --max-target-megabytes 2 --redact --no-banner
            --report-format json --report-path "$report")
    fi
    start=$(date -u +%Y-%m-%dT%H:%M:%SZ); s=$(date +%s.%N)
    "$RUNNER" "${ISO[@]}" "$bin" "${args[@]}" > "$D/logs/$tool-$mode.out" 2> "$err"
    rc=$?
    e=$(date +%s.%N)
    printf '%s\t%s\tstart=%s\telapsed_s=%.1f\trc=%s\targv=%s %s\n' "$tool" "$mode" "$start" \
      "$(echo "$e - $s" | bc)" "$rc" "$tool" "${args[*]//$D/<scratch>}" >> "$D/logs/scans.tsv"
  done
done
