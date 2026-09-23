#!/usr/bin/env bash
# Gaps 6/14: fetch the pinned OpenBao v2.6.2 linux/amd64 release into the isolated
# cache, check the GitHub asset digest and publisher checksum, and verify the
# Sigstore bundles with cosign (keyless, upstream release workflow identity).
# Network: ~76 MB archive plus small checksum/bundle files from GitHub releases.
set -uo pipefail
C=${C:-$HOME/.cache/gap-wave2-20260923/security-supply-chain}
V=2.6.2
D=$C/dl/openbao-$V; I=$C/openbao-$V; OUT=$C/work/openbao; mkdir -p "$D" "$I" "$OUT"
LOG=$OUT/install.log; : > "$LOG"
BASE=https://github.com/openbao/openbao/releases/download/v$V
A=openbao_${V}_linux_amd64.tar.gz
run() { local label=$1; shift; printf '### %s\n$ %s\n' "$label" "$*" >> "$LOG"; HOME=$C/home TUF_ROOT=$C/tuf "$@" >> "$LOG" 2>&1; local rc=$?; printf 'exit=%s\n\n' "$rc" >> "$LOG"; echo "$label exit=$rc"; }
cd "$D"
for f in "$A" "$A.sigstore.json" checksums.txt checksums.txt.sigstore.json; do
  [[ -s $f ]] || run "download $f" curl -fsSL -o "$f" "$BASE/$f"
done
run "github asset digest (from release API)" sh -c "echo '8dc11cc5fca0b539a9e352727dacb4e2d304daffcf9a66e0718ac325a20d05aa  $A' | sha256sum -c -"
run "publisher checksum list" sha256sum --ignore-missing -c checksums.txt
ISSUER=https://token.actions.githubusercontent.com
# Attempt 1 guessed a tag-ref identity and failed (exit 1, log retained); the certificate
# SAN is the release workflow on the release/2.6.x branch, pinned exactly here.
ID=https://github.com/openbao/openbao/.github/workflows/release.yml@refs/heads/release/2.6.x
run "cosign verify-blob checksums.txt" "$C/bin/cosign" verify-blob --bundle checksums.txt.sigstore.json \
  --certificate-identity "$ID" --certificate-oidc-issuer "$ISSUER" checksums.txt
run "cosign verify-blob archive" "$C/bin/cosign" verify-blob --bundle "$A.sigstore.json" \
  --certificate-identity "$ID" --certificate-oidc-issuer "$ISSUER" "$A"
cp "$A" "$OUT/$A.tampered"; printf 'x' >> "$OUT/$A.tampered"
run "NEGATIVE cosign verify-blob tampered archive" "$C/bin/cosign" verify-blob --bundle "$A.sigstore.json" \
  --certificate-identity "$ID" --certificate-oidc-issuer "$ISSUER" "$OUT/$A.tampered"
rm -f "$OUT/$A.tampered"
run "NEGATIVE cosign verify-blob wrong identity (tag ref)" "$C/bin/cosign" verify-blob --bundle "$A.sigstore.json" \
  --certificate-identity "https://github.com/openbao/openbao/.github/workflows/release.yml@refs/tags/v2.6.2" --certificate-oidc-issuer "$ISSUER" "$A"
run "extract" tar -xzf "$A" -C "$I" bao
run "bao version" "$I/bao" version
sha256sum "$I/bao" >> "$LOG"
