#!/usr/bin/env bash
# Gap 2/13: cosign keyless verification of the syft/grype checksum files, tie the
# installed binaries to the verified archives, and record gitleaks' signing status.
# Every command's exit code is written to $OUT/signatures.log; nothing is installed
# outside $C. Network: Sigstore TUF root, Rekor lookups, GitHub release API.
set -uo pipefail
C=${C:-$HOME/.cache/gap-wave2-20260923/security-supply-chain}
D=$C/dl
OUT=${OUT:-$C/work/signatures}
TOOLS=${TOOLS:-$HOME/.local/share/codex-ecosystem/tools}
mkdir -p "$OUT" "$C/home" "$C/tuf"
cd "$D"
LOG=$OUT/signatures.log
: > "$LOG"
run() {  # run LABEL CMD...
  local label=$1; shift
  printf '### %s\n$ %s\n' "$label" "$*" >> "$LOG"
  HOME=$C/home TUF_ROOT=$C/tuf "$@" >> "$LOG" 2>&1
  local rc=$?
  printf 'exit=%s\n\n' "$rc" >> "$LOG"
  echo "$label exit=$rc"
}
COSIGN=$C/bin/cosign
ISSUER=https://token.actions.githubusercontent.com

for spec in syft:1.52.0:02ba369d13b4248395b20a504eca94b0cab564d8 grype:0.119.0:b6f5194537747ee7f705f4113069ac9eb269919f; do
  IFS=: read -r tool ver commit <<<"$spec"
  sums=${tool}_${ver}_checksums.txt
  ident="https://github.com/anchore/${tool}/.github/workflows/release.yaml@refs/heads/main"
  regexp="^https://github\.com/anchore/${tool}/\.github/workflows/.+"
  run "$tool verify-blob exact identity" "$COSIGN" verify-blob \
    --certificate "$sums.pem" --signature "$sums.sig" \
    --certificate-identity "$ident" --certificate-oidc-issuer "$ISSUER" \
    --certificate-github-workflow-sha "$commit" "$sums"
  run "$tool verify-blob identity regexp" "$COSIGN" verify-blob \
    --certificate "$sums.pem" --signature "$sums.sig" \
    --certificate-identity-regexp "$regexp" --certificate-oidc-issuer "$ISSUER" "$sums"
  # Negative controls: a one-byte change to the checksum file and a wrong identity must fail.
  cp "$sums" "$OUT/$sums.tampered"; printf '\n' >> "$OUT/$sums.tampered"
  run "$tool NEGATIVE tampered blob" "$COSIGN" verify-blob \
    --certificate "$sums.pem" --signature "$sums.sig" \
    --certificate-identity "$ident" --certificate-oidc-issuer "$ISSUER" "$OUT/$sums.tampered"
  run "$tool NEGATIVE wrong identity" "$COSIGN" verify-blob \
    --certificate "$sums.pem" --signature "$sums.sig" \
    --certificate-identity "https://github.com/anchore/other/.github/workflows/release.yaml@refs/heads/main" \
    --certificate-oidc-issuer "$ISSUER" "$sums"
  run "$tool archive checksum in signed list" sha256sum --ignore-missing -c "$sums"
done
run "gitleaks archive checksum in unsigned list" sha256sum --ignore-missing -c gitleaks_8.30.1_checksums.txt

# Tie installed binaries to the verified archives.
x=$OUT/extract; rm -rf "$x"; mkdir -p "$x"/{syft,grype,gitleaks}
tar -xzf syft_1.52.0_linux_amd64.tar.gz -C "$x/syft" syft
tar -xzf grype_0.119.0_linux_amd64.tar.gz -C "$x/grype" grype
tar -xzf gitleaks_8.30.1_linux_x64.tar.gz -C "$x/gitleaks" gitleaks
{
  echo "### installed vs archive binary sha256"
  sha256sum "$x/syft/syft" "$TOOLS/syft-1.52.0/syft" "$x/grype/grype" "$TOOLS/grype-0.119.0/grype" \
    "$x/gitleaks/gitleaks" "$TOOLS/gitleaks-8.30.1/gitleaks"
} >> "$LOG"

# gitleaks provenance: release asset list and GitHub artifact attestations (public API, unauthenticated).
digest=$(sha256sum gitleaks_8.30.1_linux_x64.tar.gz | cut -d' ' -f1)
run "gitleaks release assets" curl -sS https://api.github.com/repos/gitleaks/gitleaks/releases/tags/v8.30.1 -o "$OUT/gitleaks-release.json"
python3 -c "import json,sys;print('assets:',[a['name'] for a in json.load(open(sys.argv[1]))['assets']])" "$OUT/gitleaks-release.json" >> "$LOG"
run "gitleaks attestation lookup by archive digest" curl -sS -w '\nhttp_status=%{http_code}\n' \
  "https://api.github.com/repos/gitleaks/gitleaks/attestations/sha256:$digest"
echo "done; log at $LOG"
