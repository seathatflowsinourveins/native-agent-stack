#!/usr/bin/env bash
# Repair-round fixture runs (local integration; not upstream tests). The three fixture classes of
# tests/test_gitleaks_config.py, which now read betterleaks's `null` empty report as no findings, run
# with the verified gitleaks 8.30.1 and then betterleaks 1.8.1 as the `gitleaks` on PATH (symlinks in
# shim-gl and shim-bl), with GITLEAKS_TESTS_REQUIRED=1 as in the trial job. XDG_CACHE_HOME keeps
# betterleaks's wazero cache in this directory; HOME stays, because the fingerprint test commits with git.
# run_fixtures.py prints test ids and outcome classes only and keeps tracebacks in 0600 scratch files.
set -uo pipefail
D="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
W="$1"
M=tests.test_gitleaks_config
mkdir -p "$D/iso-cache" "$D/repair"
for tool in gl bl; do
  env PATH="$D/shim-$tool:$PATH" GITLEAKS_TESTS_REQUIRED=1 XDG_CACHE_HOME="$D/iso-cache" \
    python3 "$D/run_fixtures.py" "$W" "$tool-ported" "$D/repair" \
    "$M.GitleaksPresenceTests" "$M.GitleaksConfigContextRestrictionTests" "$M.GitleaksIgnoreFingerprintTests"
  echo "$tool collector_rc=$?"
done
