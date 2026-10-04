# `shell: bash` runs with -e; turn it off so a findings exit (1) is captured and
# all three SARIF results are still written, then fail with the worst observed status.
set +e -u -o pipefail
inventory=.github/osv-scanner-lockfiles.json
frozen_config=.github/osv-scanner-frozen-macos.toml
frozen_wsl_config=.github/osv-scanner-frozen-wsl-retrieval.toml
# Scope comes from this caller, not OSV's explicit-config mechanism. Reject missing/duplicate inputs,
# config drift, changed lock digests, missing evidence, expired policy and restored replay/install routes.
python3 -m unittest \
  tests.test_osv_lockfile_coverage.LockfileInventoryTests \
  tests.test_osv_lockfile_coverage.FrozenScanTests \
  tests.test_wsl_retrieval.RetiredRunnerTests || exit "$?"
# An entry without a parser lets OSV-Scanner infer it from the file name (":<path>").
# An explicit --config applies to every input of one invocation (OSV-Scanner docs/configuration.md),
# so each frozen group has its own invocation, and ordinary entries use the config with no archive exception.
mapfile -t lockfiles < <(jq -r '.lockfiles[] | select(has("config") | not) | "--lockfile=\(.parser // ""):\(.path)"' "$inventory")
mapfile -t frozen < <(jq -r --arg config "$frozen_config" '.lockfiles[] | select(.config == $config) | "--lockfile=\(.parser // ""):\(.path)"' "$inventory")
mapfile -t frozen_wsl < <(jq -r --arg config "$frozen_wsl_config" '.lockfiles[] | select(.config == $config) | "--lockfile=\(.parser // ""):\(.path)"' "$inventory")
test "${#lockfiles[@]}" -gt 0 || exit 1
test "${#frozen[@]}" -gt 0 || exit 1
test "${#frozen_wsl[@]}" -gt 0 || exit 1
# Every entry is in exactly one scan: together the three lists are the inventory, so an entry that
# names any other config is in neither and fails here.
test "$(( ${#lockfiles[@]} + ${#frozen[@]} + ${#frozen_wsl[@]} ))" -eq "$(jq '.lockfiles | length' "$inventory")" || exit 1
# Also enforce unique inputs and the two exact archive assignments in the shell caller itself.
jq -e --arg mac_config "$frozen_config" --arg wsl_config "$frozen_wsl_config" '
  .lockfiles as $entries | ($entries | map(.path)) as $paths |
  (($paths | length) == ($paths | unique | length)) and
  ([$entries[] | select(.config == $mac_config) | .path] ==
    ["evidence/artifacts/macos-application-20260924/variant/pnpm-lock.yaml"]) and
  ([$entries[] | select(.config == $wsl_config) | .path] ==
    ["blueprints/convergence-practice/wsl-retrieval/package-lock.json"])
' "$inventory" > /dev/null || exit 1
# --no-resolve: scan the versions each file pins. Transitive resolution of the
# unlocked manifests reported versions no lockfile installs (decision record).
scan=("$RUNNER_TEMP/osv-scanner/osv-scanner" scan source --config .github/osv-scanner.toml
  --no-resolve "${lockfiles[@]}")
scan_frozen=("$RUNNER_TEMP/osv-scanner/osv-scanner" scan source --config "$frozen_config"
  --no-resolve "${frozen[@]}")
scan_frozen_wsl=("$RUNNER_TEMP/osv-scanner/osv-scanner" scan source --config "$frozen_wsl_config"
  --no-resolve "${frozen_wsl[@]}")
"${scan[@]}"
status=$?
"${scan_frozen[@]}"
frozen_status=$?
"${scan_frozen_wsl[@]}"
frozen_wsl_status=$?
statuses=("$status" "$frozen_status" "$frozen_wsl_status")
printf 'OSV primary statuses: ordinary=%s frozen-macos=%s frozen-wsl=%s\n' "$status" "$frozen_status" "$frozen_wsl_status"
if [ "$WRITE_SARIF" = true ]; then
  "${scan[@]}" --format sarif --output-file "$RUNNER_TEMP/osv-scanner/osv-scanner.sarif"
  sarif_status=$?
  "${scan_frozen[@]}" --format sarif --output-file "$RUNNER_TEMP/osv-scanner/osv-scanner-frozen-macos.sarif"
  frozen_sarif_status=$?
  "${scan_frozen_wsl[@]}" --format sarif --output-file "$RUNNER_TEMP/osv-scanner/osv-scanner-frozen-wsl-retrieval.sarif"
  frozen_wsl_sarif_status=$?
  statuses+=("$sarif_status" "$frozen_sarif_status" "$frozen_wsl_sarif_status")
  printf 'OSV SARIF statuses: ordinary=%s frozen-macos=%s frozen-wsl=%s\n' "$sarif_status" "$frozen_sarif_status" "$frozen_wsl_sarif_status"
  # 0: no vulnerabilities; 1: vulnerabilities (already reported above); other codes are scanner errors.
fi
# Preserve the worst status from every primary and SARIF invocation, including findings and scanner errors.
for code in "${statuses[@]}"; do
  if [ "$code" -gt "$status" ]; then
    status=$code
  fi
done
exit "$status"
