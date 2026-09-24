#!/usr/bin/env bash
# Gap 7: on the same NautilusTrader rc5 runtime venv, compare (1) Syft vs Trivy
# package inventories and (2) Grype vs osv-scanner and pip-audit vulnerability
# matches, each with a known-vulnerable positive control. Everything installs
# under $C. Network: trivy 0.74.0 archive (~50 MB) + its vulnerability DB,
# osv-scanner v2.6.0 binary (~58 MB) + OSV API queries, pip-audit from PyPI +
# PyPI vulnerability API queries.
set -uo pipefail
C=${C:-$HOME/.cache/gap-wave2-20260923/security-supply-chain}
VENV=${VENV:-$HOME/.local/share/codex-ecosystem/tools/adaptive-paper-20260921}
SP=$VENV/lib/python3.12/site-packages
SYFT=$HOME/.local/share/codex-ecosystem/tools/syft-1.52.0/syft
GRYPE=$HOME/.local/share/codex-ecosystem/tools/grype-0.119.0/grype
BR=$HOME/codex-ecosystem/bin/ecosystem-bounded-run
OUT=$C/work/compare; D=$C/dl/compare; mkdir -p "$OUT" "$D" "$C/trivy-cache" "$C/pip-audit-cache" "$OUT/positive"
LOG=$OUT/exits.log; MODE=${1:-all}
export GRYPE_DB_CACHE_DIR=$C/grypedb GRYPE_DB_AUTO_UPDATE=false GRYPE_CHECK_FOR_APP_UPDATE=false SYFT_CHECK_FOR_APP_UPDATE=false
run() { local label=$1; shift; local t0=$(date +%s); "$@"; local rc=$?; echo "$label exit=$rc seconds=$(( $(date +%s) - t0 ))" | tee -a "$LOG"; }
ISSUER=https://token.actions.githubusercontent.com

if [[ $MODE == install || $MODE == all ]]; then
  cd "$D"
  TV=0.74.0; TA=trivy_${TV}_Linux-64bit.tar.gz
  for f in "$TA" "$TA.sigstore.json" trivy_${TV}_checksums.txt; do
    [[ -s $f ]] || run "download $f" curl -fsSL -o "$f" "https://github.com/aquasecurity/trivy/releases/download/v$TV/$f"; done
  run trivy-asset-digest sh -c "echo '2ae6fe3ee734b7fdf11335663e18c75ea12dccc76062f09f164a3b0f8be4371a  $TA' | sha256sum -c -"
  run trivy-checksum-list sha256sum --ignore-missing -c trivy_${TV}_checksums.txt
  HOME=$C/home TUF_ROOT=$C/tuf run trivy-cosign-verify "$C/bin/cosign" verify-blob --bundle "$TA.sigstore.json" \
    --certificate-identity-regexp '^https://github\.com/aquasecurity/trivy/\.github/workflows/.+' \
    --certificate-oidc-issuer "$ISSUER" "$TA" 2> "$OUT/trivy-cosign.stderr"
  mkdir -p "$C/trivy-$TV"; tar -xzf "$TA" -C "$C/trivy-$TV" trivy
  OV=2.6.0
  [[ -s osv-scanner_linux_amd64 ]] || run download-osv curl -fsSL -o osv-scanner_linux_amd64 "https://github.com/google/osv-scanner/releases/download/v$OV/osv-scanner_linux_amd64"
  [[ -s osv-scanner_SHA256SUMS ]] || run download-osv-sums curl -fsSL -o osv-scanner_SHA256SUMS "https://github.com/google/osv-scanner/releases/download/v$OV/osv-scanner_SHA256SUMS"
  run osv-asset-digest sh -c "echo 'ca69b3d3cd08f889a49dc0a383122f71cc528b83803671df5fd874d97485b108  osv-scanner_linux_amd64' | sha256sum -c -"
  run osv-checksum-list sha256sum --ignore-missing -c osv-scanner_SHA256SUMS
  mkdir -p "$C/osv-scanner-$OV"; install -m 755 osv-scanner_linux_amd64 "$C/osv-scanner-$OV/osv-scanner"
  # Host python3 lacks ensurepip (first attempt: exit 1), so the installed uv creates the venv.
  UV=$HOME/.local/share/codex-ecosystem/tools/uv-0.12.17/uv
  run pip-audit-venv "$UV" venv --quiet --python /usr/bin/python3 "$C/pip-audit-venv"
  UV_CACHE_DIR=$C/uv-cache run pip-audit-install "$UV" pip install --quiet --python "$C/pip-audit-venv/bin/python" pip-audit==2.10.1
fi

TRIVY=$C/trivy-0.74.0/trivy; OSV=$C/osv-scanner-2.6.0/osv-scanner; PA=$C/pip-audit-venv/bin/pip-audit
if [[ $MODE == scan || $MODE == all ]]; then
  # Positive-control inputs: a pinned requirements file and matching SBOM content.
  printf 'requests==2.19.0\nurllib3==1.24.1\n' > "$OUT/positive/requirements.txt"
  # --- inventory arm ---
  run syft-venv "$SYFT" scan "dir:$SP" -o "syft-json=$OUT/syft.json" -o "cyclonedx-json=$OUT/syft.cdx.json" 2> "$OUT/syft.stderr"
  ECOSYSTEM_JOB_SECONDS=1200 run trivy-rootfs "$BR" "$TRIVY" rootfs --cache-dir "$C/trivy-cache" --scanners vuln \
    --list-all-pkgs --skip-java-db-update --format json --output "$OUT/trivy.json" "$SP" 2> "$OUT/trivy.stderr"
  run trivy-positive "$TRIVY" fs --cache-dir "$C/trivy-cache" --scanners vuln --skip-db-update --skip-java-db-update \
    --format json --output "$OUT/trivy-positive.json" "$OUT/positive" 2> "$OUT/trivy-positive.stderr"
  # --- vulnerability arm ---
  run grype-venv "$GRYPE" "sbom:$OUT/syft.json" -o json --file "$OUT/grype.json" 2> "$OUT/grype.stderr"
  run osv-venv "$OSV" scan source -L "$OUT/syft.cdx.json" --format json --output-file "$OUT/osv.json" 2> "$OUT/osv.stderr"
  run osv-positive "$OSV" scan source -L "$OUT/positive/requirements.txt" --format json --output-file "$OUT/osv-positive.json" 2> "$OUT/osv-positive.stderr"
  run pip-audit-venv-scan "$PA" --path "$SP" --format json --output "$OUT/pip-audit.json" --cache-dir "$C/pip-audit-cache" --progress-spinner off 2> "$OUT/pip-audit.stderr"
  run pip-audit-positive "$PA" -r "$OUT/positive/requirements.txt" --no-deps --disable-pip --format json \
    --output "$OUT/pip-audit-positive.json" --cache-dir "$C/pip-audit-cache" --progress-spinner off 2> "$OUT/pip-audit-positive.stderr"
  "$TRIVY" --version > "$OUT/versions.txt"; "$OSV" --version >> "$OUT/versions.txt"; "$PA" --version >> "$OUT/versions.txt"
fi
