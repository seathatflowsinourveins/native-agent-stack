#!/usr/bin/env bash
# Gaps 3/9: Syft with the binary catalogers explicitly selected over (a) the pinned
# NautilusTrader rc5 runtime venv and (b) the host root filesystem, each piped into
# Grype on the isolated database. Mode: venv | root. Output under $C/work/syft-binary.
set -uo pipefail
C=${C:-$HOME/.cache/gap-wave2-20260923/security-supply-chain}
SYFT=$HOME/.local/share/codex-ecosystem/tools/syft-1.52.0/syft
GRYPE=$HOME/.local/share/codex-ecosystem/tools/grype-0.119.0/grype
VENV=${VENV:-$HOME/.local/share/codex-ecosystem/tools/adaptive-paper-20260921}
BR=$HOME/codex-ecosystem/bin/ecosystem-bounded-run
OUT=$C/work/syft-binary; mkdir -p "$OUT" "$C/syft-cache"
export SYFT_CACHE_DIR=$C/syft-cache SYFT_CHECK_FOR_APP_UPDATE=false
export GRYPE_DB_CACHE_DIR=$C/grypedb GRYPE_DB_AUTO_UPDATE=false GRYPE_CHECK_FOR_APP_UPDATE=false
LOG=$OUT/exits.log
run() { local label=$1; shift; local t0=$(date +%s); "$@"; local rc=$?; echo "$label exit=$rc seconds=$(( $(date +%s) - t0 ))" | tee -a "$LOG"; }
# "+binary" (a tag) is rejected by syft 1.52 for "+" (exact names only); these are
# already in the directory default set, and are named here explicitly.
BIN_CATALOGERS=+binary-classifier-cataloger,+elf-binary-package-cataloger,+cargo-auditable-binary-cataloger,+go-module-binary-cataloger
MODE=${1:-venv}

if [[ $MODE == venv ]]; then
  run venv-syft "$SYFT" scan "dir:$VENV" --select-catalogers "$BIN_CATALOGERS" --source-name nautilus-rc5-venv \
    -o "syft-json=$OUT/venv.syft.json" 2> "$OUT/venv.syft.stderr"
  run venv-grype "$GRYPE" "sbom:$OUT/venv.syft.json" -o json --file "$OUT/venv.grype.json" 2> "$OUT/venv.grype.stderr"
  find "$VENV" -type f \( -name '*.so' -o -name '*.so.*' \) -printf '%P\n' | sort > "$OUT/venv-so-files.txt"
fi
if [[ $MODE == root ]]; then
  # Excluded: pseudo/runtime filesystems, Windows drive mounts, user homes, temp dirs.
  # These exclusions are coverage limits recorded in the receipt. Syft requires
  # directory-source exclusions to start with ./ (relative to the scan root).
  ECOSYSTEM_JOB_SECONDS=1200 ECOSYSTEM_JOB_MEMORY_HIGH=5G ECOSYSTEM_JOB_MEMORY_MAX=8G \
  run root-syft "$BR" "$SYFT" scan dir:/ --select-catalogers "$BIN_CATALOGERS" --source-name host-root \
    --exclude './proc/**' --exclude './sys/**' --exclude './dev/**' --exclude './mnt/**' --exclude './run/**' --exclude './tmp/**' \
    --exclude './home/**' --exclude './root/**' --exclude './lost+found/**' --exclude './var/tmp/**' \
    -o "syft-json=$OUT/root.syft.json" 2> "$OUT/root.syft.stderr"
  ECOSYSTEM_JOB_SECONDS=1200 ECOSYSTEM_JOB_MEMORY_HIGH=5G ECOSYSTEM_JOB_MEMORY_MAX=8G \
  run root-grype "$BR" "$GRYPE" "sbom:$OUT/root.syft.json" -o json --file "$OUT/root.grype.json" 2> "$OUT/root.grype.stderr"
  dpkg-query -W -f='${Package}\t${Version}\t${Architecture}\n' | sort > "$OUT/dpkg-query.tsv"
fi
if [[ $MODE == interp ]]; then
  # The Nautilus venv uses /usr/bin/python3.12 (dpkg-owned, inside the root scan). The SDK venv
  # uses a uv-managed CPython under $HOME, which the root scan excluded: scan it directly.
  PYDIR=${PYDIR:-$HOME/.local/share/codex-ecosystem/python/cpython-3.13.15-linux-x86_64-gnu}
  run interp-syft "$SYFT" scan "dir:$PYDIR" --select-catalogers "$BIN_CATALOGERS" --source-name sdk-cpython \
    -o "syft-json=$OUT/interp.syft.json" 2> "$OUT/interp.syft.stderr"
  run interp-grype "$GRYPE" "sbom:$OUT/interp.syft.json" -o json --file "$OUT/interp.grype.json" 2> "$OUT/interp.grype.stderr"
fi
if [[ $MODE == ibkr ]]; then
  # Local IBKR-side software: the installed IB Gateway 1050 program jars and bundled JRE
  # (its data/ settings directory is deliberately not read), and the IBKR adapter venv.
  GW=${GW:-$HOME/Jts/ibgateway/1050}
  for part in jars jre; do
    run "ibgw-$part-syft" "$SYFT" scan "dir:$GW/$part" --select-catalogers "$BIN_CATALOGERS" --source-name "ibgateway-1050-$part" \
      -o "syft-json=$OUT/ibgw-$part.syft.json" 2> "$OUT/ibgw-$part.syft.stderr"
    run "ibgw-$part-grype" "$GRYPE" "sbom:$OUT/ibgw-$part.syft.json" -o json --file "$OUT/ibgw-$part.grype.json" 2> "$OUT/ibgw-$part.grype.stderr"
  done
  IBV=${IBV:-$HOME/.local/share/codex-ecosystem/tools/ibkr-lane-20260922}
  run ibkr-venv-syft "$SYFT" scan "dir:$IBV" --select-catalogers "$BIN_CATALOGERS" --source-name ibkr-lane-venv \
    -o "syft-json=$OUT/ibkr-venv.syft.json" 2> "$OUT/ibkr-venv.syft.stderr"
  run ibkr-venv-grype "$GRYPE" "sbom:$OUT/ibkr-venv.syft.json" -o json --file "$OUT/ibkr-venv.grype.json" 2> "$OUT/ibkr-venv.grype.stderr"
fi
