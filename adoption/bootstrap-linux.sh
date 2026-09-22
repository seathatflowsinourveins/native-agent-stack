#!/usr/bin/env bash
# Staged 2026-09-22. Native Linux x86_64 Ubuntu/Debian adoption bootstrap.
# Ported from agent-lab .devcontainer/bootstrap-linux.sh. No account sign-in,
# secret migration, shell-profile edit, or permission bypass.
set -Eeuo pipefail

usage() {
  printf '%s\n' \
    'Usage: bash bootstrap-linux.sh --profile <id> [--skip-system-packages]' \
    '' \
    'Installs the tools pinned in adoption/pins-linux-x86_64.json for the' \
    "given profile's component_ids (from adoption/manifest.json) under" \
    'ECO_INSTALL_ROOT (default ~/.local/share/codex-ecosystem), each in an' \
    'isolated tools/<name>-<version> prefix with bin/ symlinks. Every archive' \
    'is SHA-256 verified before extraction; a pin with a null sha256 refuses' \
    'to install (fail closed). Uses sudo only for missing Ubuntu/Debian' \
    'apt prerequisites. Never edits a shell profile.'
}

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
repo_root="$(cd -- "$script_dir/.." >/dev/null 2>&1 && pwd -P)"

profile_id=""
skip_system=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile)
      [[ $# -ge 2 ]] || { printf -- '--profile requires a value.\n' >&2; exit 2; }
      profile_id="$2"
      shift 2
      ;;
    --profile=*)
      profile_id="${1#--profile=}"
      shift
      ;;
    --skip-system-packages)
      skip_system=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      exit 2
      ;;
  esac
done
[[ -n "$profile_id" ]] || { printf -- 'Missing required --profile <id>.\n' >&2; exit 2; }

[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] || {
  printf 'This verified asset set targets x86_64 Linux, not Windows/Git Bash or ARM.\n' >&2
  exit 1
}
[[ "$EUID" -ne 0 ]] || { printf 'Run as your normal Linux user, not root.\n' >&2; exit 1; }
[[ -r /etc/os-release ]] || { printf 'Cannot identify Linux distribution.\n' >&2; exit 1; }
# shellcheck disable=SC1091
. /etc/os-release
case "${ID:-}" in
  ubuntu|debian) ;;
  *) printf 'This bootstrap supports Ubuntu and Debian.\n' >&2; exit 1 ;;
esac

for required in curl git tar sha256sum realpath flock jq mktemp; do
  command -v "$required" >/dev/null || { printf 'Missing prerequisite: %s\n' "$required" >&2; exit 1; }
done

manifest_path="$repo_root/adoption/manifest.json"
pins_path="$repo_root/adoption/pins-linux-x86_64.json"
[[ -r "$manifest_path" ]] || { printf 'Missing manifest: %s\n' "$manifest_path" >&2; exit 1; }
[[ -r "$pins_path" ]] || { printf 'Missing pins file: %s\n' "$pins_path" >&2; exit 1; }

component_ids_json="$(jq -c --arg id "$profile_id" \
  '[.profiles[] | select(.id == $id) | .component_ids[]]' "$manifest_path")"
[[ "$component_ids_json" != "[]" ]] || {
  printf 'Unknown or empty profile: %s\n' "$profile_id" >&2
  exit 1
}
mapfile -t component_ids < <(printf '%s' "$component_ids_json" | jq -r '.[]')

if [[ "$skip_system" == 0 ]]; then
  packages=(ca-certificates curl git tar gzip xz-utils jq)
  missing=()
  for package in "${packages[@]}"; do
    if [[ "$(dpkg-query -W -f='${Status}' "$package" 2>/dev/null || true)" != 'install ok installed' ]]; then
      missing+=("$package")
    fi
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    command -v sudo >/dev/null || { printf 'sudo is required to install missing system packages.\n' >&2; exit 1; }
    sudo apt-get update
    sudo apt-get install -y --no-install-recommends "${missing[@]}"
  fi
fi

ecosystem_root="${ECO_INSTALL_ROOT:-$HOME/.local/share/codex-ecosystem}"
[[ "$ecosystem_root" == /* && "$ecosystem_root" != / && "$ecosystem_root" != "$HOME" ]] || {
  printf 'ECO_INSTALL_ROOT must name a dedicated absolute directory.\n' >&2; exit 1
}
mkdir -p "$ecosystem_root"
ecosystem_root="$(realpath "$ecosystem_root")"
bin_dir="$ecosystem_root/bin"
cache_dir="$ecosystem_root/downloads"
mkdir -p "$bin_dir" "$cache_dir" "$ecosystem_root/tools"
exec 9>"$ecosystem_root/bootstrap.lock"
flock -n 9 || { printf 'Another ecosystem bootstrap is running.\n' >&2; exit 1; }
stage_dir="$(mktemp -d "$ecosystem_root/staging.XXXXXXXX")"
cleanup() {
  if [[ -n "${stage_dir:-}" && "$stage_dir" == "$ecosystem_root"/staging.* && -d "$stage_dir" ]]; then
    rm -rf -- "$stage_dir"
  fi
}
trap cleanup EXIT

fetch() {
  local url="$1" checksum="$2" destination="$3"
  if [[ -f "$destination" ]] && printf '%s  %s\n' "$checksum" "$destination" | sha256sum --check --status; then
    return
  fi
  curl --fail --location --show-error --silent --retry 3 --proto '=https' --tlsv1.2 \
    "$url" --output "$destination.partial"
  printf '%s  %s\n' "$checksum" "$destination.partial" | sha256sum --check --status || {
    printf 'Checksum mismatch: %s\n' "$url" >&2; exit 1
  }
  mv -- "$destination.partial" "$destination"
}

# Node needs multiple executables symlinked from one --strip-components=1 tree.
install_node() {
  local version="$1" url="$2" sha256="$3"
  local archive="$cache_dir/node-v${version}-linux-x64.tar.xz"
  fetch "$url" "$sha256" "$archive"
  local prefix="$ecosystem_root/tools/node-$version"
  mkdir -p "$prefix"
  tar -xf "$archive" --strip-components=1 -C "$prefix"
  local executable
  for executable in node npm npx corepack; do
    if [[ -e "$prefix/bin/$executable" ]]; then
      ln -sfn "$prefix/bin/$executable" "$bin_dir/$executable"
    fi
  done
}

# uv ships both uv and uvx from one top-level archive directory.
install_uv() {
  local version="$1" url="$2" sha256="$3"
  local archive="$cache_dir/${url##*/}" extract_dir="$stage_dir/uv-$version"
  fetch "$url" "$sha256" "$archive"
  mkdir -p "$extract_dir" "$ecosystem_root/tools/uv-$version"
  tar -xf "$archive" -C "$extract_dir"
  local executable found
  for executable in uv uvx; do
    found="$(find "$extract_dir" -type f -name "$executable" | head -n1)"
    [[ -n "$found" ]] || { printf '%s missing from uv archive.\n' "$executable" >&2; exit 1; }
    install -m 0755 "$found" "$ecosystem_root/tools/uv-$version/$executable"
    ln -sfn "$ecosystem_root/tools/uv-$version/$executable" "$bin_dir/$executable"
  done
}

# Generic single-binary tarball: find a file literally named <id> and install it.
install_single_binary_tarball() {
  local id="$1" version="$2" url="$3" sha256="$4"
  local archive="$cache_dir/${url##*/}" extract_dir="$stage_dir/$id-$version"
  fetch "$url" "$sha256" "$archive"
  mkdir -p "$extract_dir" "$ecosystem_root/tools/$id-$version"
  tar -xf "$archive" -C "$extract_dir"
  local matches=()
  mapfile -t matches < <(find "$extract_dir" -type f -name "$id")
  [[ ${#matches[@]} == 1 ]] || {
    printf 'Expected exactly one %s executable in its archive, found %s.\n' "$id" "${#matches[@]}" >&2
    exit 1
  }
  install -m 0755 "${matches[0]}" "$ecosystem_root/tools/$id-$version/$id"
  ln -sfn "$ecosystem_root/tools/$id-$version/$id" "$bin_dir/$id"
}

npm_package_name() {
  # https://registry.npmjs.org/<pkg>/-/<file>.tgz -> <pkg> (scoped or plain)
  local url="$1" rest="${1#https://registry.npmjs.org/}"
  rest="${rest%%/-/*}"
  [[ "$rest" != "$url" && -n "$rest" ]] || { printf 'Unrecognized npm registry URL: %s\n' "$url" >&2; exit 1; }
  printf '%s\n' "$rest"
}

install_npm() {
  local id="$1" version="$2" url="$3" sha256="$4"
  command -v npm >/dev/null || { printf 'npm is required to install %s; install node first.\n' "$id" >&2; exit 1; }
  local archive="$cache_dir/${id}-${version}.tgz"
  fetch "$url" "$sha256" "$archive"
  local prefix="$ecosystem_root/tools/$id-$version"
  mkdir -p "$prefix"
  local package
  package="$(npm_package_name "$url")"
  npm install --global --no-audit --no-fund --prefix "$prefix" "$archive" >/dev/null
  local linked=0 executable
  if [[ -d "$prefix/bin" ]]; then
    for executable in "$prefix/bin"/*; do
      [[ -e "$executable" ]] || continue
      ln -sfn "$executable" "$bin_dir/$(basename "$executable")"
      linked=1
    done
  fi
  [[ "$linked" == 1 ]] || printf 'Note: %s (%s) published no bin/ executable; installed for its library only.\n' "$id" "$package" >&2
}

install_pip() {
  local id="$1" version="$2"
  command -v pip3 >/dev/null || command -v pip >/dev/null || {
    printf 'pip is required to install %s.\n' "$id" >&2; exit 1
  }
  local pip_cmd; pip_cmd="$(command -v pip3 || command -v pip)"
  local prefix="$ecosystem_root/tools/$id-$version"
  mkdir -p "$prefix"
  "$pip_cmd" install --no-input --target "$prefix" "${id}==${version}"
  [[ -d "$prefix/bin" ]] && for executable in "$prefix/bin"/*; do
    [[ -e "$executable" ]] && ln -sfn "$executable" "$bin_dir/$(basename "$executable")"
  done
  true
}

install_uv_tool() {
  local id="$1" version="$2"
  command -v uv >/dev/null || { printf 'uv is required to install %s; install uv first.\n' "$id" >&2; exit 1; }
  UV_TOOL_DIR="$ecosystem_root/python-tools" UV_TOOL_BIN_DIR="$bin_dir" \
    uv tool install --python 3.13 "${id}==${version}"
}

install_pin() {
  local id="$1"
  local entry
  entry="$(jq -c --arg id "$id" '.tools[] | select(.id == $id)' "$pins_path")"
  if [[ -z "$entry" ]]; then
    printf 'No pin for component %s in %s; skipping.\n' "$id" "$pins_path" >&2
    return 0
  fi
  local version kind url sha256 note
  version="$(jq -r '.version' <<<"$entry")"
  kind="$(jq -r '.kind' <<<"$entry")"
  url="$(jq -r '.url' <<<"$entry")"
  sha256="$(jq -r '.sha256' <<<"$entry")"
  note="$(jq -r '.install_note' <<<"$entry")"
  if [[ "$sha256" == "null" || -z "$sha256" ]]; then
    printf 'Refusing to install %s %s: pin has no verified sha256 (%s)\n' "$id" "$version" "$note" >&2
    exit 1
  fi
  case "$id-$kind" in
    node-tarball) install_node "$version" "$url" "$sha256" ;;
    uv-tarball) install_uv "$version" "$url" "$sha256" ;;
    *-tarball) install_single_binary_tarball "$id" "$version" "$url" "$sha256" ;;
    *-npm) install_npm "$id" "$version" "$url" "$sha256" ;;
    *-pip) install_pip "$id" "$version" ;;
    *-uv-tool) install_uv_tool "$id" "$version" ;;
    *) printf 'Unknown pin kind %s for %s.\n' "$kind" "$id" >&2; exit 1 ;;
  esac
  printf 'Installed %s %s (%s)\n' "$id" "$version" "$kind"
}

# node, uv and gh are core prerequisites the npm-kind pins and gh-based
# verification below depend on; install them before the profile's own list.
for core_id in node uv gh; do
  install_pin "$core_id"
done

for id in "${component_ids[@]}"; do
  case "$id" in
    node|uv|gh) continue ;;
  esac
  install_pin "$id"
done

export PATH="$bin_dir:$PATH"

{
  printf 'Verified executable versions at %s for profile %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$profile_id"
  git --version
  command -v node >/dev/null && node --version
  command -v npm >/dev/null && npm --version
  command -v uv >/dev/null && uv --version
  command -v gh >/dev/null && gh --version
} | tee "$ecosystem_root/installed-versions.txt"

printf '\nInstallation finished. Add %q to PATH to use it in this shell.\n' "$bin_dir"
printf '%s\n' 'Next: sign into Codex, Claude, and GitHub using their native browser login flows.' \
  'Validate the actual sandbox with Codex /permissions and Claude /sandbox before unattended work.' \
  'No model request, project migration, shell-profile change, or account sign-in was performed.'
