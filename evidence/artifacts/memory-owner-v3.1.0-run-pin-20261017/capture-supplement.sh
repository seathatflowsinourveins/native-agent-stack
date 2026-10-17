#!/usr/bin/env bash
# Supplement to capture.sh for the memory-owner run pin: the local sha256 of the two publisher sidecars, and the install.sh
# blob at the tagged commit read through the GitHub contents API. It adds files under <outputs-dir> and rewrites none of
# capture.sh's.
# Usage: capture-supplement.sh <outputs-dir> <scratch-dir>
set -euo pipefail
out="$1"; scratch="$2"
repo=akitaonrails/ai-memory
commit=11ca7c5b3b65e7fc216c7eae5a9aac67d38c11ea
base="https://github.com/$repo/releases/download/v3.1.0"
mkdir -p "$out"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
dl="$scratch/dl-$stamp"
mkdir "$dl"   # a fresh, empty directory
date -u +%Y-%m-%dT%H:%M:%SZ > "$out/supplement-recorder-time.txt"

# The two sidecars and the installer, downloaded again; the local sha256 of both sidecars (capture.sh recorded the archive's and the
# installer's), beside the digest the GitHub API gives for each asset.
for name in ai-memory-linux-x86_64.tar.gz.sha256 install.sh install.sh.sha256; do
  curl --proto '=https' --tlsv1.2 -fsSL -o "$dl/$name" "$base/$name"
done
(cd "$dl" && sha256sum ai-memory-linux-x86_64.tar.gz.sha256 install.sh.sha256) > "$out/sidecar-sha256.txt"

# install.sh at the tagged commit, through the contents API (raw media type), hashed and sized.
gh api -H "Accept: application/vnd.github.raw+json" "repos/$repo/contents/install.sh?ref=$commit" > "$dl/install.sh.at-commit"
{
  printf '%s  install.sh at %s (contents API)\n' "$(sha256sum < "$dl/install.sh.at-commit" | cut -d' ' -f1)" "$commit"
  printf 'bytes %s\n' "$(wc -c < "$dl/install.sh.at-commit")"
  cmp "$dl/install.sh" "$dl/install.sh.at-commit" && echo "identical to the release asset install.sh (cmp exit 0)"
} > "$out/install-script-blob-at-tag.txt"
echo "dl=$dl"
