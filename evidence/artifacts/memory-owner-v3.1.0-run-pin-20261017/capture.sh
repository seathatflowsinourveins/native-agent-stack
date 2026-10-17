#!/usr/bin/env bash
# Native capture of ai-memory v3.1.0's tag resolution and release checksums for the memory-owner run pin.
# Usage: capture.sh <outputs-dir> <scratch-dir>
set -euo pipefail
out="$1"; scratch="$2"
repo=akitaonrails/ai-memory
base="https://github.com/$repo/releases/download/v3.1.0"
mkdir -p "$out"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
dl="$scratch/dl-$stamp"; ext="$scratch/extract-$stamp"
mkdir "$dl" "$ext"   # fresh, empty directories
date -u +%Y-%m-%dT%H:%M:%SZ > "$out/recorder-time.txt"

# Tag resolution, verbatim.
git ls-remote "https://github.com/$repo" 'refs/tags/v3.1.0' 'refs/tags/v3.1.0^{}' > "$out/upstream-tag-resolution.txt"

# GitHub API tag ref and tag object, field-filtered (tagger e-mail dropped).
gh api "repos/$repo/git/ref/tags/v3.1.0" --jq '{ref, object: {sha: .object.sha, type: .object.type}}' > "$dl/ref.json"
tag_object="$(jq -r .object.sha "$dl/ref.json")"
gh api "repos/$repo/git/tags/$tag_object" \
  --jq '{sha, tag, message, tagger: {name: .tagger.name, date: .tagger.date}, object: {sha: .object.sha, type: .object.type}, verification: {verified: .verification.verified, reason: .verification.reason}}' > "$dl/tag.json"
jq -n --slurpfile ref "$dl/ref.json" --slurpfile tag "$dl/tag.json" \
  '{filter: "fields kept: ref, object.sha, object.type; tag sha, tag, message, tagger.name, tagger.date, object, verification.verified, verification.reason (tagger.email dropped)", git_ref: $ref[0], git_tag: $tag[0]}' \
  > "$out/github-api-tag.json"
gh api "repos/$repo/releases/tags/v3.1.0" \
  --jq '{tag_name, target_commitish, draft, prerelease, published_at, assets: [.assets[] | select(.name | test("^(ai-memory-linux-x86_64\\.tar\\.gz|install\\.sh)(\\.sha256)?$")) | {name, size, digest, browser_download_url}] | sort_by(.name)}' \
  > "$out/github-api-release-assets.json"

# Release archive, installer and their publisher sidecars, checked natively.
for name in ai-memory-linux-x86_64.tar.gz ai-memory-linux-x86_64.tar.gz.sha256 install.sh install.sh.sha256; do
  curl --proto '=https' --tlsv1.2 -fsSL -o "$dl/$name" "$base/$name"
done
(cd "$dl" && sha256sum -c ai-memory-linux-x86_64.tar.gz.sha256) > "$out/verify-release-checksum.txt"
(cd "$dl" && sha256sum -c install.sh.sha256) > "$out/verify-install-script-checksum.txt"
(cd "$dl" && sha256sum ai-memory-linux-x86_64.tar.gz install.sh) > "$out/download-sha256.txt"

# The binary inside the verified archive (extracted, never run).
tar --no-same-owner -xzf "$dl/ai-memory-linux-x86_64.tar.gz" -C "$ext" ./ai-memory
(cd "$ext" && sha256sum ai-memory) > "$out/release-binary-sha256.txt"
tar -tzf "$dl/ai-memory-linux-x86_64.tar.gz" | grep -E '^\./packaging/systemd/|^\./install\.sh$|^\./ai-memory$' > "$out/release-archive-members.txt" || true
echo "dl=$dl"
