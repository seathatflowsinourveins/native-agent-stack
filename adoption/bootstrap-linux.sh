#!/usr/bin/env bash
# Staged 2026-09-22. Native Linux x86_64 Ubuntu/Debian adoption bootstrap.
# Ported from agent-lab .devcontainer/bootstrap-linux.sh. No account sign-in,
# secret migration, shell-profile edit, or permission bypass.
set -Eeuo pipefail

usage() {
  printf '%s\n' \
    'Usage: bash bootstrap-linux.sh --profile <id> [--skip-system-packages]' \
    '                                [--allow-unpinned <id,id,...>]' \
    '                                [--configure-claude-user-profile]' \
    '' \
    'Installs the tools pinned in adoption/pins-linux-x86_64.json for the' \
    "given profile's component_ids (from adoption/manifest.json) under" \
    'ECO_INSTALL_ROOT (default ~/.local/share/codex-ecosystem), each in an' \
    'isolated tools/<name>-<version> prefix with bin/ symlinks. Every archive' \
    'is SHA-256 verified before extraction; a pin with a null sha256 refuses' \
    'to install (fail closed). A selected component with no pin at all also' \
    'fails closed (exit 3) before installing anything, unless it is named in' \
    '--allow-unpinned, in which case it is skipped and echoed to the run log.' \
    'Uses sudo only for missing Ubuntu/Debian apt prerequisites, installed' \
    'before the curl/git/tar/jq presence check unless --skip-system-packages' \
    'is given, in which case that check lists what is missing and exits 4.' \
    'After installing, checks each installed pin with the version_probe its' \
    'pin declares (bounded, stdin closed; servers are never started) and' \
    'writes installed-versions.txt; exits 5 if any probe fails.' \
    'Never edits a shell profile.'
}

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
repo_root="$(cd -- "$script_dir/.." >/dev/null 2>&1 && pwd -P)"

profile_id=""
skip_system=0
allow_unpinned_ids=()
configure_claude_user_profile=0
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
    --configure-claude-user-profile)
      # Opt-in, run only after this script prints the native-sign-in
      # reminder below: installs adoption/hooks/claude/effort-default-guard.py
      # (sha256-checked), adoption/agents/claude/*.md, and the user-scope MCP
      # servers in adoption/mcp/claude-user.json via `claude mcp add --scope
      # user` (tools/adoption/install_claude_profile.py; idempotent, and
      # requires a signed-in `claude` for the MCP step to do anything but a
      # skip). See adoption/bootstrap.md.
      configure_claude_user_profile=1
      shift
      ;;
    --allow-unpinned)
      [[ $# -ge 2 ]] || { printf -- '--allow-unpinned requires a comma-separated id list.\n' >&2; exit 2; }
      IFS=',' read -r -a _allow_unpinned_chunk <<<"$2"
      allow_unpinned_ids+=("${_allow_unpinned_chunk[@]}")
      shift 2
      ;;
    --allow-unpinned=*)
      IFS=',' read -r -a _allow_unpinned_chunk <<<"${1#--allow-unpinned=}"
      allow_unpinned_ids+=("${_allow_unpinned_chunk[@]}")
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

# Unless the caller opts out, install missing curl/git/tar/jq (and their apt
# dependencies) *before* checking for them below, so a bare Ubuntu/Debian host
# with none of them yet installed satisfies the check without a second run.
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

missing_prerequisites=()
for required in curl git tar sha256sum realpath flock jq mktemp; do
  command -v "$required" >/dev/null || missing_prerequisites+=("$required")
done
if [[ ${#missing_prerequisites[@]} -gt 0 ]]; then
  printf 'Missing prerequisites: %s\n' "${missing_prerequisites[*]}" >&2
  if [[ "$skip_system" == 1 ]]; then
    printf 'Re-run without --skip-system-packages, or install them manually first.\n' >&2
  fi
  exit 4
fi

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

# Fail closed on any selected component with no pin, before installing
# anything: install_pin's own "no pin -> skip" path only ever reaches
# components explicitly allowed via --allow-unpinned below.
all_selected_ids=(node uv gh)
for selected_id in "${component_ids[@]}"; do
  case "$selected_id" in
    node|uv|gh) continue ;;
  esac
  all_selected_ids+=("$selected_id")
done
unpinned_ids=()
for selected_id in "${all_selected_ids[@]}"; do
  pin_entry="$(jq -c --arg id "$selected_id" '.tools[] | select(.id == $id)' "$pins_path")"
  [[ -n "$pin_entry" ]] || unpinned_ids+=("$selected_id")
done
if [[ ${#unpinned_ids[@]} -gt 0 ]]; then
  unresolved_unpinned_ids=()
  for unpinned_id in "${unpinned_ids[@]}"; do
    allowed=0
    for allowed_id in "${allow_unpinned_ids[@]}"; do
      [[ "$unpinned_id" == "$allowed_id" ]] && { allowed=1; break; }
    done
    [[ "$allowed" == 1 ]] || unresolved_unpinned_ids+=("$unpinned_id")
  done
  if [[ ${#unresolved_unpinned_ids[@]} -gt 0 ]]; then
    printf 'No pin in %s for selected component(s): %s\n' "$pins_path" "${unresolved_unpinned_ids[*]}" >&2
    printf 'Pass --allow-unpinned %s to install the rest and skip these explicitly.\n' \
      "$(IFS=,; printf '%s' "${unresolved_unpinned_ids[*]}")" >&2
    exit 3
  fi
  printf 'Allowed unpinned components (--allow-unpinned): %s\n' "${unpinned_ids[*]}"
fi

ecosystem_root="${ECO_INSTALL_ROOT:-$HOME/.local/share/codex-ecosystem}"
[[ "$ecosystem_root" == /* && "$ecosystem_root" != / && "$ecosystem_root" != "$HOME" ]] || {
  printf 'ECO_INSTALL_ROOT must name a dedicated absolute directory.\n' >&2; exit 1
}
mkdir -p "$ecosystem_root"
ecosystem_root="$(realpath "$ecosystem_root")"
# Compared again after canonicalization, before any child is created: "$HOME/.",
# "$HOME/../<home>" or a symlink to HOME must not put bin/, tools/ and
# downloads/ straight into the shared home directory (-ef compares inodes).
if [[ "$ecosystem_root" == / || "$ecosystem_root" -ef "$HOME" || "$ecosystem_root" -ef / ]]; then
  printf 'ECO_INSTALL_ROOT must name a dedicated absolute directory (it resolves to %s).\n' "$ecosystem_root" >&2; exit 1
fi
bin_dir="$ecosystem_root/bin"
cache_dir="$ecosystem_root/downloads"
mkdir -p "$bin_dir" "$cache_dir" "$ecosystem_root/tools"
# Exported before any install so npm-kind and uv-tool-kind pins resolve the
# node/npm and uv symlinked here, not a pre-existing host copy (or none).
export PATH="$bin_dir:$PATH"
exec 9>"$ecosystem_root/bootstrap.lock"
flock -n 9 || { printf 'Another ecosystem bootstrap is running.\n' >&2; exit 1; }
stage_dir="$(mktemp -d "$ecosystem_root/staging.XXXXXXXX")"
cleanup() {
  # An interrupted version report leaves its probe and watchdog running in
  # their own process groups (run_version_probe, below); stop both.
  # Reaped under a silenced stderr, so bash prints no job notice for them.
  local group
  for group in "${version_probe_pid:-}" "${version_watchdog_pid:-}"; do
    if [[ -n "$group" ]]; then { kill -KILL -- "-$group" && wait "$group"; } 2>/dev/null || true; fi
  done
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

# Native self-installing binary (e.g. claude-code 2.1.280+): download,
# verify sha256, then hand off to the binary's own installer, which manages
# its own version directory and launcher and keeps auto-update working.
# Mirrors ~/codex-ecosystem/bin/bootstrap-linux.sh (round 2026-09-22,
# lines 158-171): fetch the exact per-version download, chmod it executable,
# run `"$bin" install <version>`, and leave the binary's own auto-update in
# control from there (no DISABLE_AUTOUPDATER opt-out).
#
# The pin is a floor, not a ceiling (2026-09-24): `"$bin" install <pin>`
# moves the installer's own launcher back to the pin, dropping a newer
# auto-updated release's fixes. A launcher at $HOME/.local/bin/<bin> whose
# `--version` first word ("2.1.281" of "2.1.281 (Claude Code)") is a dotted
# numeric version at or above the pin is kept: nothing is downloaded or
# installed, and install_pin logs "Kept" instead of "Installed". Fields are
# compared as base-10 numbers (2.1.99 is older than 2.1.281). No launcher, a
# failing --version, a non-numeric version or an older one takes the
# unchanged checksum-verified install. The function is identical to
# adoption/bootstrap-macos.sh's install_native, which added this floor first;
# tests/test_adoption_bootstrap.py fails if the two copies differ.
install_native() {
  # $5 is the command the native installer creates (the pin's `bin`, e.g.
  # claude-code installs ~/.local/bin/claude); it defaults to the pin id.
  local id="$1" version="$2" url="$3" sha256="$4" bin_name="${5:-$1}"
  local launcher="$HOME/.local/bin/$bin_name" installed="" keep=0 have want have_field want_field
  if [[ -x "$launcher" ]] && installed="$("$launcher" --version </dev/null 2>/dev/null)"; then
    installed="${installed%%[[:space:]]*}"
    keep=1
    case "$installed" in ''|*[!0-9.]*|.*|*.|*..*) keep=0 ;; esac
    case "$version" in ''|*[!0-9.]*|.*|*.|*..*) keep=0 ;; esac
    have="$installed" want="$version"
    while [[ "$keep" == 1 && -n "$have$want" ]]; do
      have_field="${have%%.*}" want_field="${want%%.*}"
      if [[ "$have" == *.* ]]; then have="${have#*.}"; else have=""; fi
      if [[ "$want" == *.* ]]; then want="${want#*.}"; else want=""; fi
      if (( 10#${have_field:-0} > 10#${want_field:-0} )); then break; fi
      if (( 10#${have_field:-0} < 10#${want_field:-0} )); then keep=0; fi
    done
  fi
  if [[ "$keep" == 1 ]]; then
    native_floor_kept="$installed"
    printf 'Kept installed %s %s: at or above the pinned floor %s, so nothing was downloaded or installed (installing the pin would downgrade it).\n' \
      "$id" "$installed" "$version"
  else
    local download="$cache_dir/${id}-${version}-native"
    fetch "$url" "$sha256" "$download"
    chmod 0755 "$download"
    "$download" install "$version"
  fi
  # When bin_dir is the installer's own ~/.local/bin, its launcher (a symlink
  # into ~/.local/share/claude/versions) already provides the command; writing
  # ours there would replace it with a script that execs itself.
  if [[ "$(cd "$bin_dir" && pwd -P)" == "$(cd "$HOME/.local/bin" 2>/dev/null && pwd -P)" ]]; then
    return 0
  fi
  # Remove first so the redirect never writes through an existing symlink.
  rm -f "$bin_dir/$bin_name"
  {
    printf '#!/usr/bin/env bash\n'
    printf '# Native auto-updating launcher (installed by %s install); the ecosystem no longer pins a snapshot.\n' "$id"
    # shellcheck disable=SC2016
    printf 'exec "$HOME/.local/bin/%s" "$@"\n' "$bin_name"
  } > "$bin_dir/$bin_name"
  chmod 0755 "$bin_dir/$bin_name"
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

# rtk 0.50.0's Claude hook windows `git show <rev>:<path>` blobs (a piped
# `| tail` then reads the window, not the file's end), and a rewritten `diff`
# exits 1 instead of 2 on a missing file. recipes/README.md#native-context-mode-and-hooks
# excludes both through rtk's own config. Print-only: never writes that file.
rtk_config_reminder() {
  local config="${XDG_CONFIG_HOME:-$HOME/.config}/rtk/config.toml"
  if [[ -f "$config" ]] && grep -Eq '^[[:space:]]*exclude_commands[[:space:]]*=' "$config" \
    && grep -Fq '"^git show [^ ]*:"' "$config" && grep -Fq '"diff"' "$config"; then
    return 0
  fi
  printf 'Reminder: for the Claude hook, %s needs [hooks] exclude_commands = ["^git show [^ ]*:", "diff"] (recipes/README.md#native-context-mode-and-hooks); this script does not write it.\n' "$config"
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
  # install_native sets this when it keeps an installed launcher at or above
  # the pin (the pin is a floor); it has already logged that decision.
  native_floor_kept=""
  case "$id-$kind" in
    node-tarball) install_node "$version" "$url" "$sha256" ;;
    uv-tarball) install_uv "$version" "$url" "$sha256" ;;
    *-tarball) install_single_binary_tarball "$id" "$version" "$url" "$sha256" ;;
    *-npm) install_npm "$id" "$version" "$url" "$sha256" ;;
    *-native) install_native "$id" "$version" "$url" "$sha256" "$(jq -r '.bin // .id' <<<"$entry")" ;;
    *-pip) install_pip "$id" "$version" ;;
    *-uv-tool) install_uv_tool "$id" "$version" ;;
    *) printf 'Unknown pin kind %s for %s.\n' "$kind" "$id" >&2; exit 1 ;;
  esac
  # A kept native launcher (at or above its floor) is still an installed
  # pin: the version report probes it like any other.
  installed_pin_ids+=("$id")
  [[ -z "$native_floor_kept" ]] || return 0
  printf 'Installed %s %s (%s)\n' "$id" "$version" "$kind"
  [[ "$id" != rtk ]] || rtk_config_reminder
}

# The pins this run installed, in install order; the version report below
# observes exactly these.
installed_pin_ids=()

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

# Version report ($ECO_INSTALL_ROOT/installed-versions.txt). Each pin declares
# how its installed version is observed (version_probe in the pins file), as
# nixpkgs versionCheckHook and Homebrew test blocks are declared per package,
# instead of one flag run against every file in bin_dir: MCP Inspector,
# context-mode and socraticode have no --version, and each starts a server
# (Inspector its web UI) on an unknown argument, so that loop blocked on an
# interactive terminal. An exec probe runs only the declared command, with
# stdin from /dev/null, in its own process group and under a wall-clock bound;
# an npm-metadata probe runs only bin/npm, to read the package version without
# running the package. Other executables in bin_dir are listed with their link
# target and not run. A failed probe stops the run with exit 5 once the report
# is written, before the closing steps.
# Everything from version_probe_seconds to the end of the script's report
# step is kept identical in bootstrap-macos.sh (bash 3.2); only this hook,
# the platform lines at the top of the report, differs.
version_report_platform() {
  printf '%s (%s)\n' "${PRETTY_NAME:-${ID:-linux}}" "$(uname -m)"
}

version_probe_seconds=30
version_probe_failed=0
version_probe_failed_ids=""
version_probe_pid=""
version_watchdog_pid=""

# run_version_probe SECONDS STDOUT STDERR COMMAND [ARG...]: runs COMMAND with
# stdin from /dev/null and descriptor 9 closed (bootstrap-linux.sh holds its
# flock there; nothing is open on it in bootstrap-macos.sh), sends TERM to its
# whole process group after SECONDS and KILL 2 s later, and returns its
# status, or 124 when the bound expired. Anything the probe left running in
# its group is killed once it exits. While it runs, the probe and watchdog
# group ids stay in version_probe_pid and version_watchdog_pid, so cleanup
# can stop both if the script is interrupted.
run_version_probe() {
  local seconds="$1" stdout_file="$2" stderr_file="$3" expired="$2.expired" status=0
  shift 3
  rm -f -- "$expired"
  # Job control puts each background job in its own process group, so the
  # watchdog also reaches a server the probe forked, not only the probe.
  set -m
  "$@" </dev/null >"$stdout_file" 2>"$stderr_file" 9>&- &
  version_probe_pid=$!
  (
    sleep "$seconds"
    kill -0 -- "-$version_probe_pid" 2>/dev/null || exit 0
    : >"$expired"
    kill -TERM -- "-$version_probe_pid" 2>/dev/null || exit 0
    sleep 2
    kill -KILL -- "-$version_probe_pid" 2>/dev/null || exit 0
  ) </dev/null >/dev/null 2>&1 9>&- &
  version_watchdog_pid=$!
  set +m
  # Braced so bash's own job-status notice for a killed probe is discarded too.
  { wait "$version_probe_pid"; } 2>/dev/null || status=$?
  { kill -KILL -- "-$version_probe_pid"; } 2>/dev/null || true
  # KILL, not TERM: a watchdog still starting up carries the script's own
  # TERM trap and would exit without its already-forked sleep.
  { kill -KILL -- "-$version_watchdog_pid"; wait "$version_watchdog_pid"; } 2>/dev/null || true
  version_probe_pid=""
  version_watchdog_pid=""
  if [[ -e "$expired" ]]; then
    rm -f -- "$expired"
    return 124
  fi
  return "$status"
}

# version_at_least OBSERVED FLOOR: dot-separated numeric comparison; a
# missing trailing component counts as 0 (bash 3.2: no array length).
version_at_least() {
  local observed_parts floor_parts index=0 observed_part floor_part
  IFS=. read -r -a observed_parts <<<"$1"
  IFS=. read -r -a floor_parts <<<"$2"
  while [[ -n "${observed_parts[index]:-}" || -n "${floor_parts[index]:-}" ]]; do
    observed_part="${observed_parts[index]:-0}"
    floor_part="${floor_parts[index]:-0}"
    [[ "$observed_part" =~ ^[0-9]+$ && "$floor_part" =~ ^[0-9]+$ ]] || return 1
    if ((10#$observed_part > 10#$floor_part)); then
      return 0
    elif ((10#$observed_part < 10#$floor_part)); then
      return 1
    fi
    index=$((index + 1))
  done
  return 0
}

# version_output_matches EXPECTED MATCH FILE...: "exact" finds EXPECTED as a
# whole version, not inside a longer one; "minimum" takes the first dotted
# version in the output and requires it to be at least EXPECTED.
version_output_matches() {
  local expected="$1" match="$2" pattern observed
  shift 2
  case "$match" in
    exact)
      pattern="$(printf '%s' "$expected" | sed 's/[][\.*^$+?(){}|/]/\\&/g')"
      grep -Eq "(^|[^0-9.])${pattern}([^0-9.]|\$)" "$@"
      ;;
    minimum)
      observed="$(cat -- "$@" | grep -Eo '[0-9]+(\.[0-9]+)+' | head -n 1 || true)"
      [[ -n "$observed" ]] && version_at_least "$observed" "$expected"
      ;;
    *)
      return 1
      ;;
  esac
}

# Prints the report for every pin this run installed, then every executable
# in bin_dir; counts failed pins in version_probe_failed(_ids).
write_version_report() {
  local id entry version method expected match package status observed result executable target argument seconds
  local probe_stdout="$stage_dir/version-probe.stdout" probe_stderr="$stage_dir/version-probe.stderr"
  local verified=0
  local probe_argv
  printf 'Version report at %s for profile %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$profile_id"
  printf 'Each installed pin is checked with its version_probe from %s; other executables are listed, not run (npm-metadata probes run only bin/npm).\n' "${pins_path##*/}"
  version_report_platform
  git --version
  for id in ${installed_pin_ids[@]+"${installed_pin_ids[@]}"}; do
    entry="$(jq -c --arg id "$id" '.tools[] | select(.id == $id)' "$pins_path")"
    version="$(jq -r '.version' <<<"$entry")"
    method="$(jq -r '.version_probe.method // "undeclared"' <<<"$entry")"
    expected="$(jq -r '.version_probe.expect // .version' <<<"$entry")"
    match="$(jq -r '.version_probe.match // "exact"' <<<"$entry")"
    # A pin may declare a longer bound, e.g. a first launch that the OS
    # assesses before running it.
    seconds="$(jq -r --argjson default "$version_probe_seconds" '.version_probe.timeout_seconds // $default' <<<"$entry")"
    status=0
    : >"$probe_stdout"
    : >"$probe_stderr"
    case "$method" in
      exec)
        probe_argv=("$bin_dir/$(jq -r '.version_probe.command' <<<"$entry")")
        while IFS= read -r argument; do
          probe_argv+=("$argument")
        done < <(jq -r '.version_probe.args[]?' <<<"$entry")
        printf -- '-- %s %s: %s --\n' "$id" "$version" "${probe_argv[*]#"$bin_dir"/}"
        run_version_probe "$seconds" "$probe_stdout" "$probe_stderr" ${probe_argv[@]+"${probe_argv[@]}"} || status=$?
        sed -n '1,20p' "$probe_stdout" "$probe_stderr"
        if [[ "$status" == 124 ]]; then
          result="FAILED (no exit within ${seconds}s; its process group was killed)"
        elif [[ "$status" != 0 ]]; then
          result="FAILED (exit $status)"
        elif version_output_matches "$expected" "$match" "$probe_stdout" "$probe_stderr"; then
          result="verified ($match $expected)"
        else
          result="FAILED (output does not report $match $expected)"
        fi
        ;;
      npm-metadata)
        package="$(npm_package_name "$(jq -r '.url' <<<"$entry")")"
        printf -- '-- %s %s: npm ls %s (package metadata; the package is not run) --\n' "$id" "$version" "$package"
        # npm ls exits nonzero for unrelated tree problems while still
        # printing the installed version, so the version decides the result.
        run_version_probe "$seconds" "$probe_stdout" "$probe_stderr" \
          "$bin_dir/npm" ls --global --prefix "$ecosystem_root/tools/$id-$version" --depth=0 --json "$package" || status=$?
        observed="$(jq -r --arg package "$package" '.dependencies[$package].version // empty' "$probe_stdout" 2>/dev/null || true)"
        printf '%s@%s\n' "$package" "${observed:-(not installed)}"
        if [[ "$status" == 124 ]]; then
          result="FAILED (npm ls did not exit within ${seconds}s)"
        elif [[ "$observed" == "$expected" ]]; then
          result="verified (exact $expected)"
        else
          result="FAILED (npm reports ${observed:-no installed package}, pinned $expected)"
        fi
        ;;
      *)
        printf -- '-- %s %s --\n' "$id" "$version"
        result="FAILED (no supported version_probe in ${pins_path##*/})"
        ;;
    esac
    printf 'result: %s\n' "$result"
    case "$result" in
      verified*) verified=$((verified + 1)) ;;
      *)
        version_probe_failed=$((version_probe_failed + 1))
        version_probe_failed_ids="$version_probe_failed_ids $id"
        ;;
    esac
  done
  printf -- '-- every entry in %s with its link target (this listing runs nothing) --\n' "${bin_dir##*/}"
  for executable in "$bin_dir"/*; do
    [[ -e "$executable" || -L "$executable" ]] || continue
    if [[ -L "$executable" ]]; then
      target="$(readlink "$executable")"
      case "$target" in
        "$ecosystem_root"/*) target="${target#"$ecosystem_root"/}" ;;
        "$HOME"/*) target="\$HOME/${target#"$HOME"/}" ;;
      esac
      [[ -e "$executable" ]] || target="$target (missing)"
    else
      target="(file)"
    fi
    printf '%s -> %s\n' "${executable##*/}" "$target"
  done
  printf 'summary: %s verified, %s failed\n' "$verified" "$version_probe_failed"
}

version_report="$ecosystem_root/installed-versions.txt"
printf 'Checking installed versions (at most %ss per probe unless its pin declares more)...\n' "$version_probe_seconds"
write_version_report >"$version_report"
cat -- "$version_report"
if [[ "$version_probe_failed" -gt 0 ]]; then
  printf '\nVersion check failed for:%s. The report is in %s; nothing was removed.\n' \
    "$version_probe_failed_ids" "$version_report" >&2
  printf 'Stopped before the PATH hint and --configure-claude-user-profile: fix or re-pin those components, then re-run this script.\n' >&2
  exit 5
fi

printf '\nInstallation finished. Add %q to PATH to use it in this shell.\n' "$bin_dir"
printf '%s\n' 'Next: sign into Codex, Claude, and GitHub using their native browser login flows.' \
  'Validate the actual sandbox with Codex /permissions and Claude /sandbox before unattended work.' \
  'No model request, project migration, shell-profile change, or account sign-in was performed.'

if [[ "$configure_claude_user_profile" == 1 ]]; then
  command -v python3 >/dev/null || { printf 'python3 is required for --configure-claude-user-profile.\n' >&2; exit 1; }
  printf '\nConfiguring the Claude Code user-scope profile (guard hook, agents, MCP servers)...\n'
  python3 "$repo_root/tools/adoption/install_claude_profile.py" --claude-bin "$bin_dir/claude" --eco-root "$ecosystem_root"
else
  printf '\nAfter native Claude sign-in, run:\n'
  printf '  python3 %q/tools/adoption/install_claude_profile.py --eco-root %q --claude-bin %q\n' "$repo_root" "$ecosystem_root" "$bin_dir/claude"
  printf 'to install the guard hook, agents and user-scope MCP servers (or re-run this script with --configure-claude-user-profile).\n'
fi
