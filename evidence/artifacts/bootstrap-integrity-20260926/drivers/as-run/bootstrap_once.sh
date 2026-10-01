#!/usr/bin/env bash
# local_integration driver (self-written; not an upstream test and not CI).
# Runs one copy of adoption/bootstrap-linux.sh, byte-identical to SCRIPT, from a scratch
# checkout skeleton whose adoption/manifest.json holds one synthetic profile "e2e", so only the
# named pins (plus the node, uv and gh every run installs) are installed from their real pinned
# upstream artifacts over the network. Everything the run writes stays under WORK: HOME and the
# XDG directories, ECO_INSTALL_ROOT (unless ECO is given), the npm cache and user config; uv reads
# no config file (UV_NO_CONFIG=1), never downloads a Python (UV_PYTHON_DOWNLOADS=never) and caches
# in UV_CACHE (shared between runs when the caller passes the same directory).
#   usage: bootstrap_once.sh LABEL SCRIPT PINS WORK UV_CACHE PROFILE_JSON [ECO] [SEED_DIR]
#   SEED_DIR: node/uv/gh archives copied into downloads/ first; fetch() re-verifies each one's sha256
#   before use, so seeding only saves bandwidth.
set -uo pipefail
label="$1" script="$2" pins="$3" work="$4" uv_cache="$5" profile="$6" eco="${7:-$4/eco}" seed="${8:-}"
root="$work/root-$label"
rm -rf "$root" "$work/home-$label" "$work/npm-cache-$label"
mkdir -p "$root/adoption" "$work/home-$label" "$work/npm-cache-$label" "$eco/downloads" "$uv_cache"
cp "$script" "$root/adoption/bootstrap-linux.sh"
cp "$pins" "$root/adoption/pins-linux-x86_64.json"
cmp -s "$script" "$root/adoption/bootstrap-linux.sh" || { echo "copy differs" >&2; exit 90; }
printf '{"schema_version":1,"profiles":[{"id":"e2e","component_ids":%s}]}\n' "$profile" \
  >"$root/adoption/manifest.json"
if [[ -n "$seed" ]]; then
  for archive in "$seed"/node-v*-linux-x64.tar.xz "$seed"/uv-x86_64-unknown-linux-gnu.tar.gz "$seed"/gh_*_linux_amd64.tar.gz; do
    [[ -f "$archive" ]] && cp -p "$archive" "$eco/downloads/"
  done
fi
: >"$work/empty-npmrc"
printf '[%s] script sha256 %s\n' "$label" "$(sha256sum <"$root/adoption/bootstrap-linux.sh" | cut -d' ' -f1)"
printf '[%s] pins sha256   %s\n' "$label" "$(sha256sum <"$root/adoption/pins-linux-x86_64.json" | cut -d' ' -f1)"
printf '[%s] profile       %s\n' "$label" "$profile"
printf '[%s] started       %s\n' "$label" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
env HOME="$work/home-$label" XDG_CONFIG_HOME="$work/home-$label/.config" \
  XDG_DATA_HOME="$work/home-$label/.local/share" XDG_CACHE_HOME="$work/home-$label/.cache" \
  XDG_STATE_HOME="$work/home-$label/.local/state" \
  ECO_INSTALL_ROOT="$eco" UV_CACHE_DIR="$uv_cache" UV_NO_CONFIG=1 UV_PYTHON_DOWNLOADS=never \
  npm_config_cache="$work/npm-cache-$label" NPM_CONFIG_USERCONFIG="$work/empty-npmrc" \
  npm_config_update_notifier=false DO_NOT_TRACK=1 MCP_AUTO_OPEN_ENABLED=false \
  timeout 1800 bash "$root/adoption/bootstrap-linux.sh" --profile e2e --skip-system-packages \
  </dev/null >"$work/$label.log" 2>&1
rc=$?
printf '[%s] ended         %s\n' "$label" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '[%s] bootstrap exit %s\n' "$label" "$rc"
exit 0
