#!/usr/bin/env bash
# Drafted 2026-09-22. Native macOS (Apple Silicon) adoption bootstrap, ported
# section for section from adoption/bootstrap-linux.sh. NOT ACCEPTED: no macOS
# host has run this script; only shimmed --plan runs on Linux exist. No account
# sign-in, secret migration, shell-profile edit, or permission bypass.
#
# Keep this script bash 3.2 compatible: a stock Mac has /bin/bash 3.2, so no
# mapfile, no associative arrays, no ${var,,}.
set -Eeuo pipefail

usage() {
  printf '%s\n' \
    'Usage: bash bootstrap-macos.sh --profile <id> [--skip-system-packages]' \
    '                               [--allow-unpinned <id,id,...>] [--plan]' \
    '' \
    'Installs the tools pinned in adoption/pins-macos-arm64.json for the' \
    "given profile's component_ids (from adoption/manifest.json) under" \
    'ECO_INSTALL_ROOT (default ~/.local/share/codex-ecosystem), each in an' \
    'isolated tools/<name>-<version> prefix with bin/ symlinks. Every archive' \
    'is SHA-256 verified with shasum -a 256 before extraction; a pin with a' \
    'null sha256 refuses to install (fail closed). A selected component with' \
    'no pin at all also fails closed (exit 3) before installing anything, and' \
    'in --plan mode too, unless it is named in --allow-unpinned, in which case' \
    'it is skipped and echoed to the run log; socraticode, documented on' \
    'adoption/platforms/macos-arm64.md as having no reviewed darwin-arm64' \
    'archive in this draft, is skipped the same way without the flag.' \
    'Uses Homebrew only for a missing jq prerequisite, installed before the' \
    'curl/git/tar/jq presence check unless --skip-system-packages is given,' \
    'in which case that check lists what is missing and exits 4.' \
    'Never edits a shell profile.' \
    '' \
    '  --plan  resolve and print each pinned component (version, asset,' \
    '          sha256) without any network access or installation; still' \
    '          exits 1 on a pin with no verified sha256 and 3 on a selected' \
    '          component with no pin at all.'
}

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
repo_root="$(cd -- "$script_dir/.." >/dev/null 2>&1 && pwd -P)"

profile_id=""
skip_system=0
plan_mode=0
allow_unpinned_ids=()
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
    --allow-unpinned)
      [[ $# -ge 2 ]] || { printf -- '--allow-unpinned requires a comma-separated id list.\n' >&2; exit 2; }
      IFS=',' read -r -a _allow_unpinned_chunk <<<"$2"
      allow_unpinned_ids+=(${_allow_unpinned_chunk[@]+"${_allow_unpinned_chunk[@]}"})
      shift 2
      ;;
    --allow-unpinned=*)
      IFS=',' read -r -a _allow_unpinned_chunk <<<"${1#--allow-unpinned=}"
      allow_unpinned_ids+=(${_allow_unpinned_chunk[@]+"${_allow_unpinned_chunk[@]}"})
      shift
      ;;
    --plan)
      plan_mode=1
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

# uname is resolved through PATH on purpose: the offline tests shim it.
[[ "$(uname -s)" == Darwin && "$(uname -m)" == arm64 ]] || {
  printf 'This verified asset set targets Apple Silicon macOS (Darwin/arm64), not Linux, Intel Macs or Rosetta.\n' >&2
  exit 1
}
[[ "$EUID" -ne 0 ]] || { printf 'Run as your normal macOS user, not root.\n' >&2; exit 1; }
command -v sw_vers >/dev/null || { printf 'Cannot identify the macOS release (sw_vers missing).\n' >&2; exit 1; }
macos_version="$(sw_vers -productVersion)"

# jq is the only prerequisite Homebrew may supply here; everything else ships
# with macOS or the Command Line Tools. Like the Linux apt block, this install
# runs *before* the presence check below, so a Mac that has no jq yet satisfies
# that check without a second run. shasum replaces Linux sha256sum.
if [[ "$skip_system" == 0 && "$plan_mode" == 0 ]] && ! command -v jq >/dev/null; then
  command -v brew >/dev/null || {
    printf 'Homebrew is required to install the missing jq prerequisite; install it from https://brew.sh or rerun with --skip-system-packages.\n' >&2
    exit 1
  }
  brew install jq
fi

missing_prerequisites=()
missing_prerequisite_count=0
for required in curl git tar shasum unzip jq mktemp; do
  if ! command -v "$required" >/dev/null; then
    missing_prerequisites+=("$required")
    missing_prerequisite_count=$((missing_prerequisite_count + 1))
  fi
done
if [[ "$missing_prerequisite_count" -gt 0 ]]; then
  printf 'Missing prerequisites: %s\n' "${missing_prerequisites[*]}" >&2
  if [[ "$skip_system" == 1 ]]; then
    printf 'Re-run without --skip-system-packages, or install them manually first (jq: brew install jq).\n' >&2
  fi
  exit 4
fi

manifest_path="$repo_root/adoption/manifest.json"
pins_path="$repo_root/adoption/pins-macos-arm64.json"
[[ -r "$manifest_path" ]] || { printf 'Missing manifest: %s\n' "$manifest_path" >&2; exit 1; }
[[ -r "$pins_path" ]] || { printf 'Missing pins file: %s\n' "$pins_path" >&2; exit 1; }

component_ids_json="$(jq -c --arg id "$profile_id" \
  '[.profiles[] | select(.id == $id) | .component_ids[]]' "$manifest_path")"
[[ "$component_ids_json" != "[]" ]] || {
  printf 'Unknown or empty profile: %s\n' "$profile_id" >&2
  exit 1
}
component_ids=()
while IFS= read -r component_id; do
  [[ -n "$component_id" ]] || continue
  component_ids+=("$component_id")
done < <(printf '%s' "$component_ids_json" | jq -r '.[]')

# Fail closed on any selected component with no pin, before installing
# anything and before --plan prints a single line: install_pin's own
# "no pin -> skip" path only ever reaches components allowed here.
#
# socraticode has no reviewed darwin-arm64 release archive in this draft and is
# documented as skipped on adoption/platforms/macos-arm64.md (it is not a
# required_command of this profile), so it is allowed by default exactly like
# an explicit --allow-unpinned id: skipped, echoed, never installed. The Linux
# script needs no such list because every component it selects is pinned.
documented_unpinned_ids=(socraticode)
allowed_unpinned_ids=("${documented_unpinned_ids[@]}" ${allow_unpinned_ids[@]+"${allow_unpinned_ids[@]}"})
all_selected_ids=(node uv gh)
for selected_id in ${component_ids[@]+"${component_ids[@]}"}; do
  case "$selected_id" in
    node|uv|gh) continue ;;
  esac
  all_selected_ids+=("$selected_id")
done
unpinned_ids=()
unpinned_count=0
for selected_id in "${all_selected_ids[@]}"; do
  pin_entry="$(jq -c --arg id "$selected_id" '.tools[] | select(.id == $id)' "$pins_path")"
  if [[ -z "$pin_entry" ]]; then
    unpinned_ids+=("$selected_id")
    unpinned_count=$((unpinned_count + 1))
  fi
done
if [[ "$unpinned_count" -gt 0 ]]; then
  unresolved_unpinned_ids=()
  unresolved_count=0
  for unpinned_id in "${unpinned_ids[@]}"; do
    allowed=0
    for allowed_id in "${allowed_unpinned_ids[@]}"; do
      [[ "$unpinned_id" == "$allowed_id" ]] && { allowed=1; break; }
    done
    if [[ "$allowed" == 0 ]]; then
      unresolved_unpinned_ids+=("$unpinned_id")
      unresolved_count=$((unresolved_count + 1))
    fi
  done
  if [[ "$unresolved_count" -gt 0 ]]; then
    printf 'No pin in %s for selected component(s): %s\n' "$pins_path" "${unresolved_unpinned_ids[*]}" >&2
    printf 'Pass --allow-unpinned %s to install the rest and skip these explicitly.\n' \
      "$(IFS=,; printf '%s' "${unresolved_unpinned_ids[*]}")" >&2
    exit 3
  fi
  printf 'Allowed unpinned components (documented skip or --allow-unpinned): %s\n' "${unpinned_ids[*]}"
fi

# Homebrew formulae float; the version record below is the retained evidence.
if [[ "$skip_system" == 0 && "$plan_mode" == 0 ]]; then
  command -v brew >/dev/null || {
    printf 'Homebrew is required for the system prerequisites; install it from https://brew.sh or rerun with --skip-system-packages.\n' >&2
    exit 1
  }
fi

ecosystem_root="${ECO_INSTALL_ROOT:-$HOME/.local/share/codex-ecosystem}"
[[ "$ecosystem_root" == /* && "$ecosystem_root" != / && "$ecosystem_root" != "$HOME" ]] || {
  printf 'ECO_INSTALL_ROOT must name a dedicated absolute directory.\n' >&2; exit 1
}
mkdir -p "$ecosystem_root"
# macOS has no realpath in the base system; cd + pwd -P canonicalizes instead.
ecosystem_root="$(cd -- "$ecosystem_root" >/dev/null 2>&1 && pwd -P)"
# Compared again after canonicalization, before any child is created: "$HOME/.",
# "$HOME/../<home>" or a symlink to HOME must not put bin/, tools/ and
# downloads/ straight into the shared home directory.
home_canonical="$(cd -- "$HOME" >/dev/null 2>&1 && pwd -P)" || home_canonical="$HOME"
[[ "$ecosystem_root" != / && "$ecosystem_root" != "$home_canonical" ]] || {
  printf 'ECO_INSTALL_ROOT must name a dedicated absolute directory (it resolves to %s).\n' "$ecosystem_root" >&2; exit 1
}
bin_dir="$ecosystem_root/bin"
cache_dir="$ecosystem_root/downloads"
mkdir -p "$bin_dir" "$cache_dir" "$ecosystem_root/tools"
# Exported before any install so npm-kind pins resolve the node/npm symlinked
# here, not a pre-existing host copy (or none).
export PATH="$bin_dir:$PATH"
# macOS has no flock(1); an atomic mkdir is the portable mutual exclusion.
lock_dir="$ecosystem_root/bootstrap.lock.d"
# lock_held flips to 1 only after this process created the lock directory, so
# cleanup can never remove a lock another bootstrap is holding.
lock_held=0
stage_dir=""
cleanup() {
  if [[ -n "${stage_dir:-}" && "$stage_dir" == "$ecosystem_root"/staging.* && -d "$stage_dir" ]]; then
    rm -rf -- "$stage_dir"
  fi
  if [[ "${lock_held:-0}" == 1 && -d "$lock_dir" ]]; then
    rmdir "$lock_dir" 2>/dev/null || true
  fi
}
# Installed before the lock is taken: a failure between mkdir and the first
# command after it (mktemp, for one) must still release this run's lock.
trap cleanup EXIT
if mkdir "$lock_dir" 2>/dev/null; then
  lock_held=1
else
  printf 'Another ecosystem bootstrap is running (%s exists).\n' "$lock_dir" >&2
  exit 1
fi
stage_dir="$(mktemp -d "$ecosystem_root/staging.XXXXXXXX")"

fetch() {
  local url="$1" checksum="$2" destination="$3"
  if [[ -f "$destination" ]] && printf '%s  %s\n' "$checksum" "$destination" | shasum -a 256 --check --status; then
    return
  fi
  curl --fail --location --show-error --silent --retry 3 --proto '=https' --tlsv1.2 \
    "$url" --output "$destination.partial"
  printf '%s  %s\n' "$checksum" "$destination.partial" | shasum -a 256 --check --status || {
    printf 'Checksum mismatch: %s\n' "$url" >&2; exit 1
  }
  mv -- "$destination.partial" "$destination"
}

# find -print -quit instead of `find | head -n1`: BSD and GNU find both support
# it, and it avoids a pipefail-visible SIGPIPE on the producer side.
find_one() {
  local directory="$1" name="$2"
  find "$directory" -type f -name "$name" -print -quit
}

# Node needs multiple executables symlinked from one --strip-components=1 tree.
install_node() {
  local version="$1" url="$2" sha256="$3"
  local archive="$cache_dir/node-v${version}-darwin-arm64.tar.xz"
  fetch "$url" "$sha256" "$archive"
  local prefix="$ecosystem_root/tools/node-$version"
  mkdir -p "$prefix"
  # bsdtar on macOS reads .tar.xz without a separate xz binary.
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
    found="$(find_one "$extract_dir" "$executable")"
    [[ -n "$found" ]] || { printf '%s missing from uv archive.\n' "$executable" >&2; exit 1; }
    install -m 0755 "$found" "$ecosystem_root/tools/uv-$version/$executable"
    ln -sfn "$ecosystem_root/tools/uv-$version/$executable" "$bin_dir/$executable"
  done
}

# gh publishes a zip (not a tarball) for macOS; the binary is at
# gh_<version>_macOS_arm64/bin/gh inside it.
install_gh_zip() {
  local version="$1" url="$2" sha256="$3"
  local archive="$cache_dir/${url##*/}" extract_dir="$stage_dir/gh-$version"
  fetch "$url" "$sha256" "$archive"
  mkdir -p "$extract_dir" "$ecosystem_root/tools/gh-$version"
  unzip -q -o "$archive" -d "$extract_dir"
  local expected="$extract_dir/gh_${version}_macOS_arm64/bin/gh" found
  if [[ -f "$expected" ]]; then
    found="$expected"
  else
    found="$(find_one "$extract_dir" gh)"
  fi
  [[ -n "$found" ]] || { printf 'gh missing from %s.\n' "$archive" >&2; exit 1; }
  install -m 0755 "$found" "$ecosystem_root/tools/gh-$version/gh"
  ln -sfn "$ecosystem_root/tools/gh-$version/gh" "$bin_dir/gh"
}

# Generic single-binary tarball: find a file literally named <id> and install it.
install_single_binary_tarball() {
  local id="$1" version="$2" url="$3" sha256="$4"
  local archive="$cache_dir/${url##*/}" extract_dir="$stage_dir/$id-$version"
  fetch "$url" "$sha256" "$archive"
  mkdir -p "$extract_dir" "$ecosystem_root/tools/$id-$version"
  tar -xf "$archive" -C "$extract_dir"
  local candidate found="" count=0
  while IFS= read -r candidate; do
    count=$((count + 1))
    found="$candidate"
  done < <(find "$extract_dir" -type f -name "$id")
  [[ "$count" == 1 ]] || {
    printf 'Expected exactly one %s executable in its archive, found %s.\n' "$id" "$count" >&2
    exit 1
  }
  install -m 0755 "$found" "$ecosystem_root/tools/$id-$version/$id"
  ln -sfn "$ecosystem_root/tools/$id-$version/$id" "$bin_dir/$id"
}

# The macOS llama.cpp asset keeps every executable next to its dylibs in one
# flat directory (observed with tar -tzf: no build/bin path), so the whole
# directory is installed and bin/llama-server is a wrapper, not a symlink --
# a bare symlink would run the binary with dyld looking beside the symlink.
install_llama_cpp() {
  local version="$1" url="$2" sha256="$3"
  local archive="$cache_dir/${url##*/}" extract_dir="$stage_dir/llama-cpp-$version"
  fetch "$url" "$sha256" "$archive"
  local prefix="$ecosystem_root/tools/llama-cpp-$version"
  mkdir -p "$extract_dir" "$prefix"
  tar -xf "$archive" -C "$extract_dir"
  local server source_dir
  server="$(find_one "$extract_dir" llama-server)"
  [[ -n "$server" ]] || { printf 'llama-server missing from the llama.cpp archive.\n' >&2; exit 1; }
  source_dir="$(cd -- "$(dirname -- "$server")" >/dev/null 2>&1 && pwd -P)"
  cp -R "$source_dir/." "$prefix/"
  # Written as a single-quoted POSIX literal (each ' becomes '\''), so a $, `,
  # " or \ in the install path stays data when the wrapper runs. sed, not
  # ${var//...}: backslash handling in that replacement differs between the
  # stock bash 3.2 and bash 4.3+.
  local quoted_prefix
  quoted_prefix="'$(printf '%s' "$prefix" | sed "s/'/'\\\\''/g")'"
  cat >"$bin_dir/llama-server" <<WRAPPER
#!/bin/sh
# Generated by adoption/bootstrap-macos.sh; do not edit.
llama_prefix=$quoted_prefix
DYLD_LIBRARY_PATH="\$llama_prefix\${DYLD_LIBRARY_PATH:+:\$DYLD_LIBRARY_PATH}"
export DYLD_LIBRARY_PATH
exec "\$llama_prefix/llama-server" "\$@"
WRAPPER
  chmod 0755 "$bin_dir/llama-server"
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
  if [[ "$plan_mode" == 1 ]]; then
    printf 'plan %-13s %-10s %-9s %s sha256=%s\n' "$id" "$version" "$kind" "${url##*/}" "$sha256"
    return 0
  fi
  case "$id-$kind" in
    node-tarball) install_node "$version" "$url" "$sha256" ;;
    uv-tarball) install_uv "$version" "$url" "$sha256" ;;
    gh-zip) install_gh_zip "$version" "$url" "$sha256" ;;
    llama-cpp-tarball) install_llama_cpp "$version" "$url" "$sha256" ;;
    *-tarball) install_single_binary_tarball "$id" "$version" "$url" "$sha256" ;;
    *-npm) install_npm "$id" "$version" "$url" "$sha256" ;;
    *) printf 'Unknown pin kind %s for %s.\n' "$kind" "$id" >&2; exit 1 ;;
  esac
  printf 'Installed %s %s (%s)\n' "$id" "$version" "$kind"
}

# node, uv and gh are core prerequisites the npm-kind pins and gh-based
# verification below depend on; install them before the profile's own list.
for core_id in node uv gh; do
  install_pin "$core_id"
done

for id in ${component_ids[@]+"${component_ids[@]}"}; do
  case "$id" in
    node|uv|gh) continue ;;
  esac
  install_pin "$id"
done

if [[ "$plan_mode" == 1 ]]; then
  printf 'Plan only for profile %s on macOS %s: nothing was downloaded or installed.\n' "$profile_id" "$macos_version"
  exit 0
fi

{
  printf 'Verified executable versions at %s for profile %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$profile_id"
  printf 'macOS %s (%s)\n' "$macos_version" "$(uname -m)"
  git --version
  # Homebrew formulae float to whatever was current at install time; record the
  # resolved versions here so the retained log keeps them.
  if command -v brew >/dev/null; then
    printf -- '-- brew list --versions --\n'
    brew list --versions || printf 'brew list --versions exited %s\n' "$?"
  else
    printf -- '-- brew not installed; no formula versions recorded --\n'
  fi
  # Every symlink or wrapper actually placed in bin_dir gets its own --version
  # run, not a fixed subset, so the retained log matches what was really
  # executed.
  for installed_executable in "$bin_dir"/*; do
    [[ -e "$installed_executable" ]] || continue
    installed_name="$(basename "$installed_executable")"
    printf -- '-- %s --\n' "$installed_name"
    "$installed_executable" --version 2>&1 || printf '%s --version exited %s\n' "$installed_name" "$?"
  done
} | tee "$ecosystem_root/installed-versions.txt"

printf '\nInstallation finished. Add %q to PATH to use it in this shell.\n' "$bin_dir"
printf '%s\n' 'Next: sign into Codex, Claude, and GitHub using their native browser login flows.' \
  'launchd agents, the llama.cpp Metal embedding endpoint and every acceptance test remain unrun on this platform.' \
  'No model request, project migration, shell-profile change, or account sign-in was performed.'
