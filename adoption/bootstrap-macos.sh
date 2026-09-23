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
    'it is skipped and echoed to the run log.' \
    'Installs any of jq, python@3.13, ripgrep, coreutils, restic and' \
    'shellcheck that brew list --versions reports missing, before the' \
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

# Homebrew supplies six formulae this profile still leaves floating: jq (a
# script prerequisite), python@3.13 (a fresh Mac's system python3 is 3.9, below
# the acceptance_target in adoption/manifest.json), ripgrep, coreutils, restic
# and shellcheck (macos-arm64.md's own `brew install jq python@3.13 ripgrep
# coreutils restic shellcheck` line). jq is installed first and alone, right
# here, because the --profile/pins validation further down already shells
# out to it; the other five are deferred until after that validation
# succeeds (below the unpinned fail-closed check), so a bad --profile or an
# unresolved pin fails fast without installing five brew formulae the run is
# about to abort on anyway. `command -v jq` is the presence oracle for jq
# specifically (its formula name and command name match); the deferred five
# use `brew list --versions <formula>` instead (not `command -v`), since
# python@3.13 and coreutils install commands under other names, so a
# name-based check would under- or over-report what is actually installed.
brew_formulae=(jq python@3.13 ripgrep coreutils restic shellcheck)
if [[ "$skip_system" == 0 && "$plan_mode" == 0 ]] && ! command -v jq >/dev/null; then
  command -v brew >/dev/null || {
    printf 'Homebrew is required to install the missing jq prerequisite; install it from https://brew.sh or rerun with --skip-system-packages.\n' >&2
    exit 1
  }
  brew install jq
elif [[ "$skip_system" == 0 && "$plan_mode" == 1 ]]; then
  printf 'plan brew formulae (installed only if brew list --versions reports them missing): %s\n' "${brew_formulae[*]}"
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
# socraticode now has a reviewed npm pin (adoption/pins-macos-arm64.json), the
# same --ignore-scripts convention recipes/README.md documents for Linux, so no
# selected component is exempted from a pin by default any more.
# documented_unpinned_ids stays as the mechanism --allow-unpinned itself uses,
# now empty, so a future undocumented gap still fails closed instead of
# silently reusing a stale skip list. The Linux script needs no such list
# because every component it selects is pinned.
documented_unpinned_ids=()
allowed_unpinned_ids=(${documented_unpinned_ids[@]+"${documented_unpinned_ids[@]}"} ${allow_unpinned_ids[@]+"${allow_unpinned_ids[@]}"})
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
    for allowed_id in ${allowed_unpinned_ids[@]+"${allowed_unpinned_ids[@]}"}; do
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

# jq was already ensured above (the validation that just ran needed it); the
# remaining five formulae only matter to actual tool installation from here
# on, so they wait until --profile and every selected component's pin have
# already validated. Bash 3.2 supports this slice (introduced in bash 3.0).
remaining_brew_formulae=("${brew_formulae[@]:1}")
if [[ "$skip_system" == 0 && "$plan_mode" == 0 ]]; then
  command -v brew >/dev/null || {
    printf 'Homebrew is required to install the missing prerequisite formulae (%s); install it from https://brew.sh or rerun with --skip-system-packages.\n' \
      "${remaining_brew_formulae[*]}" >&2
    exit 1
  }
  missing_formulae=()
  missing_formula_count=0
  for formula in "${remaining_brew_formulae[@]}"; do
    if ! brew list --versions "$formula" >/dev/null 2>&1; then
      missing_formulae+=("$formula")
      missing_formula_count=$((missing_formula_count + 1))
    fi
  done
  if [[ "$missing_formula_count" -gt 0 ]]; then
    brew install "${missing_formulae[@]}"
  fi
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
# -ef compares device and inode, so a differently-cased spelling of HOME on a
# case-insensitive APFS volume is refused as well.
if [[ "$ecosystem_root" == / || "$ecosystem_root" == "$home_canonical" || "$ecosystem_root" -ef "$HOME" || "$ecosystem_root" -ef / ]]; then
  printf 'ECO_INSTALL_ROOT must name a dedicated absolute directory (it resolves to %s).\n' "$ecosystem_root" >&2; exit 1
fi
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

# Canonicalizes a path (resolving every symlink in whatever prefix of it
# already exists) so a string comparison against what Node's require.resolve
# reports is not defeated by a symlinked ancestor -- macOS's /var ->
# /private/var (also /tmp -> /private/tmp, and a symlinked TMPDIR-based test
# fixture root on any platform) is the exact case that broke the
# install_platform_dependency containment/resolution checks below: Node
# realpath-resolves symlinks by default when it locates a module, so a
# hand-built expected path using the ORIGINAL (non-canonical) prefix spelling
# never matched. Deliberately does NOT shell out to a `realpath` binary: a
# stock Mac (this script's own test suite enforces this) is not guaranteed
# to have one pre-macOS 13. python3's `os.path.realpath` is used instead --
# it never requires the path to exist either, unlike most `realpath`
# implementations, which matters for a platform dependency's nested
# directory before it is ever fetched -- and, only if python3 is somehow
# unavailable, `cd -P && pwd -P` for an existing directory, or a manual walk
# up to the nearest existing ancestor for anything else (a file, or a path
# that does not exist yet). A stock Mac has bash 3.2 but no other guarantee,
# so this avoids arrays and `[[ =~ ]]`.
canonical_path() {
  local target="$1"
  if [[ -e "$target" ]]; then
    if command -v python3 >/dev/null 2>&1; then
      local via_python3
      via_python3="$(python3 -c 'import os, sys
print(os.path.realpath(sys.argv[1]))' "$target" 2>/dev/null)" && [[ -n "$via_python3" ]] && {
        printf '%s\n' "$via_python3"; return
      }
    fi
    if [[ -d "$target" ]]; then
      (cd -P -- "$target" >/dev/null 2>&1 && pwd -P) && return
    fi
  fi
  # $target does not exist (or every canonicalizer above failed): walk up to
  # the nearest existing ancestor, canonicalize only that, and reattach the
  # non-existent remainder unchanged -- matching os.path.realpath's own
  # semantics for a path whose tail has not been created yet.
  local remainder="" walk="$target"
  while [[ "$walk" != "/" && -n "$walk" && ! -e "$walk" ]]; do
    if [[ -z "$remainder" ]]; then
      remainder="$(basename -- "$walk")"
    else
      remainder="$(basename -- "$walk")/$remainder"
    fi
    walk="$(dirname -- "$walk")"
  done
  local canonical_walk="$walk"
  if [[ -d "$walk" ]]; then
    canonical_walk="$(cd -P -- "$walk" >/dev/null 2>&1 && pwd -P)" || canonical_walk="$walk"
  fi
  if [[ -n "$remainder" ]]; then
    printf '%s/%s\n' "$canonical_walk" "$remainder"
  else
    printf '%s\n' "$canonical_walk"
  fi
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

# codex and claude-code each carry a platform_dependency in
# pins-macos-arm64.json: the darwin-arm64 optional dependency npm itself
# resolves and installs at `npm install` time (the real native binary), which
# is not covered by this tool's own sha256 archive check above.
#
# This does NOT trust npm's own automatic, unverified fetch of it, and does
# NOT try to read it back afterward: measured directly against npm 11.19.0 on
# this project's own host, `npm install --global --prefix <dir> <pkg>` writes
# no lockfile at all (neither `<dir>/lib/node_modules/.package-lock.json` nor
# any package-lock.json anywhere under the prefix), and every installed
# package.json's `_integrity` field is absent (npm 7+ no longer writes it).
# Every already-installed npm-kind prefix on this host confirms the same
# shape. A platform-specific optional dependency is in any case placed
# NESTED under the parent package's own node_modules by npm's dependency
# placement algorithm, not at the top level this pin's `name` would suggest
# checking.
#
# Measured directly on this host (npm 11.19.0): a plain `<alias>@file:<path>`
# top-level install (this function's earlier design) is NOT what the parent's
# own require() actually finds, because installing the WRAPPER package
# itself already auto-fetches this same optional dependency, unverified, and
# nests it under the wrapper's own node_modules -- and Node's resolution
# checks that nested copy before ever considering a top-level sibling.
# --omit=optional, --no-optional and NPM_CONFIG_OMIT=optional were each
# tried against a real fixture (a plain optionalDependency, no lockfile,
# `npm install --global --prefix <dir> <pkg>`); none of them suppressed the
# physical on-disk fetch -- npm's own docs describe `omit` in terms of a
# package-lock.json this install path never has. Pre-placing verified
# content at the nested path before installing the wrapper was also tried;
# npm still overwrote it during the wrapper's own install ("changed N
# packages"). So this instead: (1) installs the wrapper with
# --ignore-scripts, deferring its lifecycle scripts so nothing consumes the
# unverified fetch yet; (2) asks Node itself, via require.resolve with the
# wrapper's own directory as the search path, exactly where it would resolve
# this dependency from (nested, in every case measured); (3) deletes that
# path and extracts the independently sha256-verified tarball there
# instead (falling back to a top-level alias if Node found nothing there at
# all, e.g. a genuine platform mismatch); (4) re-verifies resolution and the
# resolved package's own version against the pin, fail closed on either
# mismatch; (5) then runs `npm rebuild` for the wrapper, which is npm's own
# documented way to run the lifecycle scripts an --ignore-scripts install
# deferred, now that the dependency it resolves is the verified one.
# claude-code's own postinstall (install.cjs) does exactly this: it calls
# require.resolve for its platform package and copies/hard-links from
# wherever that resolves into its own bin/claude.exe -- verified end to end
# with a real npm install + real npm rebuild against a fixture that mimics
# that exact copy-on-postinstall shape, confirming the final bin/ file
# carries the verified bytes, not the unverified ones npm fetched first.
# codex has no lifecycle scripts at all; it resolves its platform package at
# every invocation of bin/codex.js, so step (5) is a no-op for it and step
# (3)'s replacement alone is what matters. A component with no
# platform_dependency pin is a silent no-op. Step (2) only ever trusts an
# EXACT string match between what require.resolve reports and the one nested
# path this wrapper's own node_modules would place this dependency at
# (computed independently, never derived from `resolved` itself); anything
# else -- including a decoy resolved from NODE_PATH/GLOBAL_FOLDERS outside
# the prefix entirely, see the comment at the containment check below -- is
# never trusted enough to delete. Step (4) re-verifies both the resolved
# package.json's `version` against the pin's `version` AND its own `name`
# against the pin's `resolved_package`, fail closed on either mismatch, so a
# same-version fixture published under the wrong package name cannot pass.
# Every path compared or deleted here is canonicalized first (`prefix` on
# entry, and independently whatever Node itself reports), because Node
# realpath-resolves symlinks by default when it locates a module: on a real
# Mac, `/var` is a symlink to `/private/var`, and a prefix built under
# `$TMPDIR` (or any other symlinked ancestor) would otherwise never
# string-equal what require.resolve reports, tripping the fail-closed path on
# a perfectly good install (see canonical_path's own comment above).
install_platform_dependency() {
  local id="$1" prefix="$2" wrapper_ignore_scripts="${3:-false}"
  prefix="$(canonical_path "$prefix")"
  local dep
  dep="$(jq -c --arg id "$id" '.tools[] | select(.id == $id) | .platform_dependency // empty' "$pins_path")"
  [[ -n "$dep" && "$dep" != "null" ]] || return 0
  local dep_name dep_url dep_sha256 dep_version dep_resolved_package
  dep_name="$(jq -r '.name' <<<"$dep")"
  dep_url="$(jq -r '.url' <<<"$dep")"
  dep_sha256="$(jq -r '.sha256' <<<"$dep")"
  dep_version="$(jq -r '.version' <<<"$dep")"
  dep_resolved_package="$(jq -r '.resolved_package' <<<"$dep")"
  if [[ "$dep_sha256" == "null" || -z "$dep_sha256" ]]; then
    printf 'Refusing %s: platform dependency %s has no verified sha256 in %s (fail closed).\n' \
      "$id" "$dep_name" "$pins_path" >&2
    exit 1
  fi
  local archive="$cache_dir/${id}-platform-dependency.tgz"
  fetch "$dep_url" "$dep_sha256" "$archive"

  local wrapper_url package
  wrapper_url="$(jq -r --arg id "$id" '.tools[] | select(.id == $id) | .url' "$pins_path")"
  package="$(npm_package_name "$wrapper_url")"
  local wrapper_dir="$prefix/lib/node_modules/$package"
  local expected_nested="$wrapper_dir/node_modules/$dep_name/package.json"
  local resolved=""
  resolved="$(node -e '
    try {
      console.log(require.resolve(process.argv[1] + "/package.json", { paths: [process.argv[2]] }));
    } catch (error) {
      process.exit(1);
    }
  ' "$dep_name" "$wrapper_dir" 2>/dev/null)" || resolved=""
  # Node already realpath-resolves symlinks when it locates a module (unless
  # --preserve-symlinks is set), so this is normally a no-op; canonicalizing
  # it here too, independently of $expected_nested's own canonical prefix,
  # is the "realpath what Node reports" half of the fix -- belt and braces
  # against a Node build or flag where that default does not hold.
  [[ -n "$resolved" ]] && resolved="$(canonical_path "$resolved")"

  local target_dir
  if [[ "$resolved" == "$expected_nested" ]]; then
    target_dir="$(dirname -- "$resolved")"
    rm -rf -- "$target_dir"
  else
    # Node's require.resolve, even given an explicit `paths` array, still
    # searches its GLOBAL_FOLDERS fallback (NODE_PATH entries,
    # $HOME/.node_modules, etc. -- Node's own module docs) -- measured
    # directly: setting NODE_PATH to a decoy directory made this resolve
    # OUTSIDE the prefix entirely. Only the EXACT nested path this wrapper's
    # own node_modules would use is ever trusted enough to delete; anything
    # else (a genuinely absent nested copy, a platform mismatch, or a decoy
    # resolved from outside the prefix) falls back to a top-level alias
    # inside this prefix, never touching whatever `resolved` actually named.
    target_dir="$prefix/lib/node_modules/$dep_name"
  fi
  mkdir -p "$target_dir"
  local extract_dir="$stage_dir/${id}-platform-dependency"
  rm -rf -- "$extract_dir"
  mkdir -p "$extract_dir"
  tar -xzf "$archive" -C "$extract_dir"
  cp -R "$extract_dir/package/." "$target_dir/"
  rm -rf -- "$extract_dir"

  local verify
  verify="$(node -e '
    const fs = require("fs");
    const resolvedPath = require.resolve(process.argv[1] + "/package.json", { paths: [process.argv[2]] });
    // fs.realpathSync canonicalizes both sides explicitly here (not the
    // shell-side canonical_path helper): resolvedPath normally already has
    // every symlink resolved by require.resolve itself, and argv[3] was
    // built from the bash-canonicalized target_dir variable, but a
    // symlinked ancestor introduced between the two calls (or a Node build
    // with --preserve-symlinks) must not defeat this fail-closed comparison
    // either way.
    const expectedPath = fs.realpathSync(process.argv[3]);
    const canonicalResolvedPath = fs.realpathSync(resolvedPath);
    if (canonicalResolvedPath !== expectedPath) {
      console.error("resolved to " + canonicalResolvedPath + ", expected " + expectedPath);
      process.exit(1);
    }
    const pkg = require(resolvedPath);
    console.log(pkg.version);
    console.log(pkg.name);
  ' "$dep_name" "$wrapper_dir" "$target_dir/package.json" 2>&1)" || {
    printf 'Refusing %s: platform dependency %s does not resolve to %s after installing the verified copy (fail closed): %s\n' \
      "$id" "$dep_name" "$target_dir/package.json" "$verify" >&2
    exit 1
  }
  local verify_version verify_name
  verify_version="$(sed -n '1p' <<<"$verify")"
  verify_name="$(sed -n '2p' <<<"$verify")"
  if [[ "$verify_version" != "$dep_version" ]]; then
    printf 'Refusing %s: platform dependency %s resolves as version %s, pinned as %s (fail closed).\n' \
      "$id" "$dep_name" "$verify_version" "$dep_version" >&2
    exit 1
  fi
  if [[ "$verify_name" != "$dep_resolved_package" ]]; then
    printf 'Refusing %s: platform dependency %s resolves with package.json name %s, pinned resolved_package is %s (fail closed).\n' \
      "$id" "$dep_name" "$verify_name" "$dep_resolved_package" >&2
    exit 1
  fi
  printf 'Installed and verified platform dependency %s@%s (%s) for %s (resolves from %s)\n' \
    "$dep_name" "$verify_version" "$verify_name" "$id" "$wrapper_dir"

  if [[ "$wrapper_ignore_scripts" != "true" ]]; then
    # npm's own documented way to run the lifecycle scripts the
    # --ignore-scripts install (in install_npm) deferred, now that the
    # dependency it resolves is the verified one. --ignore-scripts=false is
    # explicit: a user-level .npmrc with ignore-scripts=true would otherwise
    # make this call return early without running anything.
    npm rebuild --global --no-audit --no-fund --ignore-scripts=false --prefix "$prefix" "$package" >/dev/null

    local binary_check
    binary_check="$(jq -c '.postinstall_binary_check // empty' <<<"$dep")"
    if [[ -n "$binary_check" && "$binary_check" != "null" ]]; then
      # A wrapper whose own postinstall copies/hard-links from the platform
      # dependency into its own bin/ (claude-code's install.cjs) can only be
      # confirmed by comparing what actually landed there against the
      # already fully verified source, byte for byte -- cmp works whether
      # install.cjs used a hardlink or fell back to a plain copy.
      local platform_file wrapper_file
      platform_file="$(jq -r '.platform_file' <<<"$binary_check")"
      wrapper_file="$(jq -r '.wrapper_file' <<<"$binary_check")"
      if ! cmp -s "$wrapper_dir/$wrapper_file" "$target_dir/$platform_file"; then
        printf 'Refusing %s: %s does not match the verified %s byte for byte after npm rebuild (fail closed; a lifecycle script may have used an unverified source).\n' \
          "$id" "$wrapper_dir/$wrapper_file" "$target_dir/$platform_file" >&2
        exit 1
      fi
      printf 'Verified %s is byte-identical to the verified platform dependency binary %s\n' \
        "$wrapper_dir/$wrapper_file" "$target_dir/$platform_file"
    fi
  fi
}

install_npm() {
  local id="$1" version="$2" url="$3" sha256="$4" ignore_scripts="${5:-false}"
  command -v npm >/dev/null || { printf 'npm is required to install %s; install node first.\n' "$id" >&2; exit 1; }
  local archive="$cache_dir/${id}-${version}.tgz"
  fetch "$url" "$sha256" "$archive"
  local final_prefix="$ecosystem_root/tools/$id-$version"
  final_prefix="$(canonical_path "$final_prefix")"
  local package
  package="$(npm_package_name "$url")"
  local has_platform_dependency=0
  if [[ "$(jq -r --arg id "$id" '.tools[] | select(.id == $id) | .platform_dependency // empty' "$pins_path")" != "" ]]; then
    has_platform_dependency=1
  fi

  local prefix="$final_prefix"
  if [[ "$has_platform_dependency" == 1 ]]; then
    # Staged, not installed directly into a live prefix: a re-run into an
    # already-populated final_prefix would otherwise leave a window where
    # the wrapper's newly-updated files point at whatever platform
    # dependency npm's own install just auto-fetched, unverified, before
    # install_platform_dependency's fix-up below replaces it. mv onto the
    # same filesystem is a single atomic rename, so the live final_prefix is
    # always either the old, complete install or the new one, never a
    # partially verified one in between; bin_dir's existing symlinks (from a
    # prior install of this same id/version, if any) keep resolving to a
    # real, fully verified prefix throughout.
    prefix="$stage_dir/${id}-${version}-staged"
    rm -rf -- "$prefix"
  fi
  mkdir -p "$prefix"
  prefix="$(canonical_path "$prefix")"

  local npm_install_args=(--global --no-audit --no-fund --prefix "$prefix")
  if [[ "$ignore_scripts" == "true" || "$has_platform_dependency" == 1 ]]; then
    # A platform_dependency needs the wrapper's own lifecycle scripts
    # deferred until install_platform_dependency has replaced whatever npm
    # auto-fetched with the verified copy; see that function's comment.
    npm_install_args+=(--ignore-scripts)
  fi
  npm install "${npm_install_args[@]}" "$archive" >/dev/null
  if [[ "$has_platform_dependency" == 1 ]]; then
    install_platform_dependency "$id" "$prefix" "$ignore_scripts"
    # Rename the old prefix aside, move the staged one in, then delete the
    # old one -- NOT `rm -rf "$final_prefix"` followed by `mv`, which (fixed
    # here; found by Codex's own failure injection) left a real window where
    # final_prefix did not exist at all if this process died between the two:
    # every bin_dir symlink into it, and the old, previously fully verified
    # install, would both be gone with nothing to replace them yet. `mv` on
    # the same filesystem (stage_dir is always under ecosystem_root, so this
    # always holds) is a single rename(2) per call, so final_prefix is never
    # missing for longer than the gap between two such renames, and -- unlike
    # the old design -- a crash in that gap leaves the old install fully
    # intact and recoverable at final_prefix.previous.$$, never silently
    # deleted with nothing in its place.
    local previous_prefix=""
    if [[ -e "$final_prefix" ]]; then
      previous_prefix="${final_prefix}.previous.$$"
      rm -rf -- "$previous_prefix"
      mv -- "$final_prefix" "$previous_prefix"
    fi
    mv -- "$prefix" "$final_prefix"
    [[ -n "$previous_prefix" ]] && rm -rf -- "$previous_prefix"
    prefix="$final_prefix"
  fi

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
  local version kind url sha256 note ignore_scripts
  version="$(jq -r '.version' <<<"$entry")"
  kind="$(jq -r '.kind' <<<"$entry")"
  url="$(jq -r '.url' <<<"$entry")"
  sha256="$(jq -r '.sha256' <<<"$entry")"
  note="$(jq -r '.install_note' <<<"$entry")"
  ignore_scripts="$(jq -r '.ignore_scripts // false' <<<"$entry")"
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
    *-npm) install_npm "$id" "$version" "$url" "$sha256" "$ignore_scripts" ;;
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
