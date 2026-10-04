#!/usr/bin/env bash
# Scratch-only setup for the ai-memory upstream test runs: official rustup
# (checksum verified before this script), pinned-tag shallow clones, the
# toolchain rust-toolchain.toml pins, and `cargo fetch --locked`.
set -euo pipefail
S="$(cd "$(dirname "$0")" && pwd)"
export RUSTUP_HOME="$S/rust/rustup" CARGO_HOME="$S/rust/cargo"
export PATH="$CARGO_HOME/bin:/usr/bin:/bin"
export RUSTUP_INIT_SKIP_PATH_CHECK=yes
mkdir -p "$S/out" "$S/tags"
log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

if [ ! -x "$CARGO_HOME/bin/rustup" ]; then
  chmod +x "$S/dl/rustup-init"
  log "rustup-init -y --no-modify-path --profile minimal --default-toolchain none"
  "$S/dl/rustup-init" -y --no-modify-path --profile minimal --default-toolchain none
fi
rustup --version

declare -A COMMIT=(
  [v2.3.2]=353841d91618d20b110b208de284a74d0b960379
  [v2.4.0]=b1b25219b507cf56cb7334ac1a408dc9b09eaa50
  [v2.4.1]=433a19f3d54dea287571b1423591db2a89965fa9
)
for tag in v2.3.2 v2.4.0 v2.4.1; do
  dir="$S/tags/$tag"
  if [ ! -d "$dir/.git" ]; then
    log "git clone --depth 1 --branch $tag"
    git clone --quiet --depth 1 --branch "$tag" https://github.com/akitaonrails/ai-memory.git "$dir"
  fi
  head="$(git -C "$dir" rev-parse HEAD)"
  log "$tag HEAD $head expected ${COMMIT[$tag]}"
  [ "$head" = "${COMMIT[$tag]}" ] || { log "COMMIT MISMATCH for $tag"; exit 3; }
  git -C "$dir" status --porcelain | head -5
  cat "$dir/rust-toolchain.toml"
  # rust-toolchain.toml selects the toolchain inside the checkout; rustup
  # installs it (channel, profile and components) on first use.
  (cd "$dir" && rustup show active-toolchain || rustup toolchain install)
  (cd "$dir" && rustc --version --verbose && cargo --version --verbose)
  log "cargo fetch --locked ($tag)"
  (cd "$dir" && cargo fetch --locked)
done
log "setup done"
