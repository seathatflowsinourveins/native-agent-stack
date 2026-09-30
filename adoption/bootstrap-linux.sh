#!/usr/bin/env bash
# Staged 2026-09-22. Native Linux x86_64 Ubuntu/Debian adoption bootstrap.
# Ported from agent-lab .devcontainer/bootstrap-linux.sh. No account sign-in,
# secret migration, or permission bypass; the only shell-profile edit is the
# managed PATH block the opt-in --configure-full-profile appends to ~/.profile.
set -Eeuo pipefail

usage() {
  printf '%s\n' \
    'Usage: bash bootstrap-linux.sh --profile <id> [--skip-system-packages]' \
    '                                [--allow-unpinned <id,id,...>]' \
    '                                [--configure-claude-user-profile]' \
    '                                [--configure-full-profile --host <name>' \
    '                                 [--skip <step>]...]' \
    '' \
    'Installs the tools pinned in adoption/pins-linux-x86_64.json for the' \
    "given profile's component_ids (from adoption/manifest.json) under" \
    'ECO_INSTALL_ROOT (default ~/.local/share/codex-ecosystem), each in an' \
    'isolated tools/<name>-<version> prefix with bin/ symlinks. Every archive' \
    'is SHA-256 verified before extraction; a pin with a null sha256 refuses' \
    'to install (fail closed), except a uv-tool-from-git pin (serena), which' \
    'has no archive to hash and instead pins and verifies an exact git commit.' \
    'A selected component with no pin at all also' \
    'fails closed (exit 3) before installing anything, unless it is named in' \
    '--allow-unpinned, in which case it is skipped and echoed to the run log.' \
    'Uses sudo only for missing Ubuntu/Debian apt prerequisites, installed' \
    'before the curl/git/tar/jq presence check unless --skip-system-packages' \
    'is given, in which case that check lists what is missing and exits 4.' \
    'After installing, checks each installed pin with the version_probe its' \
    'pin declares (bounded, stdin closed; servers are never started) and' \
    'writes installed-versions.txt; exits 5 if any probe fails.' \
    'Never edits a shell profile, except the managed PATH block that' \
    '--configure-full-profile appends to ~/.profile. That flag then applies' \
    'the whole user profile in order, each step skippable with --skip:' \
    "  ${full_profile_steps[*]}" \
    'It runs only from a checkout at origin/main (exit 1 otherwise, before' \
    'installing anything), needs --host <name> (adoption/hosts/<name>.json)' \
    'unless claude-settings and codex-lane are skipped, and exits 6 when a' \
    'step fails; every step is idempotent, so fix the cause and re-run.'
}

# --configure-full-profile's steps, in the order they run (adoption/bootstrap.md, step 2).
full_profile_steps=(claude-profile claude-settings claude-md skills codex-lane path-block login-shell)

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
repo_root="$(cd -- "$script_dir/.." >/dev/null 2>&1 && pwd -P)"

profile_id=""
skip_system=0
allow_unpinned_ids=()
configure_claude_user_profile=0
configure_full_profile=0
full_profile_host=""
full_profile_skips=()
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
    --configure-full-profile)
      # Opt-in, after native sign-in: what --configure-claude-user-profile
      # does, then the rest of the user profile, each step through the
      # repository's own tool (full_profile_* below; adoption/bootstrap.md,
      # step 2). Refused unless this checkout is at origin/main.
      configure_full_profile=1
      shift
      ;;
    --host)
      [[ $# -ge 2 ]] || { printf -- '--host requires a value.\n' >&2; exit 2; }
      full_profile_host="$2"
      shift 2
      ;;
    --host=*)
      full_profile_host="${1#--host=}"
      shift
      ;;
    --skip)
      [[ $# -ge 2 ]] || { printf -- '--skip requires a step name.\n' >&2; exit 2; }
      IFS=',' read -r -a _skip_chunk <<<"$2"
      full_profile_skips+=("${_skip_chunk[@]}")
      shift 2
      ;;
    --skip=*)
      IFS=',' read -r -a _skip_chunk <<<"${1#--skip=}"
      full_profile_skips+=("${_skip_chunk[@]}")
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

# full_profile_selected STEP: whether --configure-full-profile runs STEP (it is not named in --skip).
full_profile_selected() {
  local skipped
  for skipped in ${full_profile_skips[@]+"${full_profile_skips[@]}"}; do
    [[ "$skipped" != "$1" ]] || return 1
  done
  return 0
}
if [[ "$configure_full_profile" != 1 ]]; then
  [[ ${#full_profile_skips[@]} -eq 0 && -z "$full_profile_host" ]] || {
    printf -- '--skip and --host apply only with --configure-full-profile.\n' >&2; exit 2
  }
else
  for skipped in ${full_profile_skips[@]+"${full_profile_skips[@]}"}; do
    case " ${full_profile_steps[*]} " in
      *" $skipped "*) ;;
      *) printf 'Unknown --skip step: %s (steps: %s)\n' "$skipped" "${full_profile_steps[*]}" >&2; exit 2 ;;
    esac
  done
  # render_config.py needs this host's values for the settings and Codex templates.
  if full_profile_selected claude-settings || full_profile_selected codex-lane; then
    [[ -n "$full_profile_host" ]] || {
      printf -- '--configure-full-profile needs --host <name> for its claude-settings and codex-lane steps: adoption/hosts/<name>.json, a copy of adoption/hosts/example.json with this host'"'"'s values (or --skip both).\n' >&2
      exit 2
    }
    [[ "$full_profile_host" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]] || { printf 'Invalid --host name: %s\n' "$full_profile_host" >&2; exit 2; }
    [[ -r "$repo_root/adoption/hosts/$full_profile_host.json" ]] || {
      printf 'No host value file adoption/hosts/%s.json: copy adoption/hosts/example.json and fill in this host'"'"'s values.\n' "$full_profile_host" >&2
      exit 2
    }
  fi
fi

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

# --configure-full-profile applies the profile main documents, so it runs only
# from a checkout whose HEAD is origin's main; both commits are printed, and the
# refusal comes before anything is installed.
if [[ "$configure_full_profile" == 1 ]]; then
  checkout_head="$(git -C "$repo_root" rev-parse --verify --quiet 'HEAD^{commit}' 2>/dev/null || true)"
  # git asks for credentials on the terminal, not on stdin, so the prompt itself is turned off.
  origin_main="$(GIT_TERMINAL_PROMPT=0 timeout 60 git -C "$repo_root" ls-remote origin refs/heads/main </dev/null 2>/dev/null | awk 'NR == 1 { print $1 }' || true)"
  printf 'This checkout (git rev-parse HEAD):        %s\n' "${checkout_head:-unknown}"
  printf 'origin main (git ls-remote origin main):   %s\n' "${origin_main:-unknown}"
  if [[ -z "$checkout_head" || -z "$origin_main" || "$checkout_head" != "$origin_main" ]]; then
    printf 'Refusing --configure-full-profile: this checkout is not at origin/main. Run it from a clone at origin/main (git fetch origin && git checkout --detach origin/main); a release checkout follows the per-step commands in adoption/bootstrap.md instead.\n' >&2
    exit 1
  fi
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

verify_sha256() {
  # Prefer macOS's native checker when available; Linux also supports the
  # GNU coreutils fallback. Both consume checksum lines on standard input.
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 --check --status
  else
    sha256sum --check --status
  fi
}

fetch() {
  local url="$1" checksum="$2" destination="$3"
  if [[ -f "$destination" ]] && printf '%s  %s\n' "$checksum" "$destination" | verify_sha256; then
    return
  fi
  curl --fail --location --show-error --silent --retry 3 --proto '=https' --tlsv1.2 \
    "$url" --output "$destination.partial"
  printf '%s  %s\n' "$checksum" "$destination.partial" | verify_sha256 || {
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

# $5 is the pin's ignore_scripts field as install_pin reads it ("true" or
# "false"): "true" adds --ignore-scripts, so npm runs no lifecycle script of
# the package or of any dependency (socraticode), as bootstrap-macos.sh's
# install_npm does.
install_npm() {
  local id="$1" version="$2" url="$3" sha256="$4" ignore_scripts="${5:-false}"
  command -v npm >/dev/null || { printf 'npm is required to install %s; install node first.\n' "$id" >&2; exit 1; }
  local archive="$cache_dir/${id}-${version}.tgz"
  fetch "$url" "$sha256" "$archive"
  local prefix="$ecosystem_root/tools/$id-$version"
  mkdir -p "$prefix"
  local package
  package="$(npm_package_name "$url")"
  local npm_install_args=(--global --no-audit --no-fund --prefix "$prefix")
  if [[ "$ignore_scripts" == "true" ]]; then
    npm_install_args+=(--ignore-scripts)
  fi
  npm install "${npm_install_args[@]}" "$archive" >/dev/null
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
# `--version` first word ("2.1.284" of "2.1.284 (Claude Code)") is a dotted
# numeric version at or above the pin is kept: nothing is downloaded or
# installed, and install_pin logs "Kept" instead of "Installed". Fields are
# compared as base-10 numbers (2.1.99 is older than 2.1.284). No launcher, a
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
    if [[ "$bin_name" == claude ]]; then
      # Interactive default effort max (docs/decisions/2026-09-29-max-default-effort.md): the client cannot save max, so the
      # documented --effort flag is added, and only when nothing has chosen an effort. The quoted heredoc keeps $HOME and $@ literal.
      cat <<'LAUNCHER_EFFORT'
# Interactive default effort: max. Claude Code cannot save max in settings (effortLevel and modelSettings take low to
# xhigh) and CLAUDE_CODE_EFFORT_LEVEL would override every --effort, /effort and child effort, so the documented --effort
# flag is added here, and only when nothing has chosen an effort: stdin and stdout are a terminal, no -p/--print (also as
# a short-flag cluster such as -pc), no --effort, no CLAUDE_CODE_EFFORT_LEVEL, nothing after a "--", and a client at
# 2.1.284 or newer (on 2.1.281 a max session turned Ultracode's orchestration off). An operand that merely equals one of
# these flags, such as the value of --system-prompt, also suppresses the default. To bypass, pass --effort <level> or run
# ~/.local/bin/claude directly.
if [ -t 0 ] && [ -t 1 ] && [ -z "${CLAUDE_CODE_EFFORT_LEVEL+x}" ]; then
  for arg in "$@"; do
    case "$arg" in
      --) break ;;
      -p* | -[!-]*p* | --print | --print=* | --effort | --effort=*) exec "$HOME/.local/bin/claude" "$@" ;;
    esac
  done
  version="$("$HOME/.local/bin/claude" --version 2>/dev/null < /dev/null)"
  version="${version%%[[:space:]]*}"
  case "$version" in
    [0-9]*.[0-9]*.[0-9]*)
      major="${version%%.*}"; rest="${version#*.}"; minor="${rest%%.*}"; patch="${rest#*.}"; patch="${patch%%.*}"
      case "$major$minor$patch" in
        *[!0-9]*) ;;
        *)
          if [ "$((10#$major))" -gt 2 ] || { [ "$((10#$major))" -eq 2 ] && { [ "$((10#$minor))" -gt 1 ] ||
            { [ "$((10#$minor))" -eq 1 ] && [ "$((10#$patch))" -ge 284 ]; }; }; }; then
            exec "$HOME/.local/bin/claude" --effort max "$@"
          fi ;;
      esac ;;
  esac
fi
LAUNCHER_EFFORT
    fi
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
  # $3 (always given: install_pin below passes the pin's "package" field,
  # falling back to its own "id" in the jq expression itself) is the actual
  # installable spec when it differs from the component id -- e.g.
  # headroom's PyPI distribution is "headroom-ai[mcp]", not "headroom".
  # $4 and $5 are the pin's url and sha256. A wheel url (headroom) is
  # consumed: fetch downloads that wheel and verifies its sha256 (exit 1 on
  # a mismatch, before uv runs), and uv installs the local file as the
  # direct reference "<package> @ file://<wheel>", which keeps the extras and
  # which uv refuses when the wheel's filename names another distribution. A
  # direct reference carries no ==version, so the filename's version must
  # equal the pin's first. The wheel's own dependencies still resolve from
  # uv's index, and uv's receipt records the wheel's path under downloads/.
  # An sdist url (markitdown, tavily-cli) is not consumed: uv resolves
  # "$package==$version" from its index, and that sha256 remains the
  # cross-check its install_note describes.
  local id="$1" version="$2" package="$3" url="$4" sha256="$5"
  command -v uv >/dev/null || { printf 'uv is required to install %s; install uv first.\n' "$id" >&2; exit 1; }
  local spec="${package}==${version}"
  if [[ "$url" == *.whl ]]; then
    # {distribution}-{version}(-{build tag})?-{python}-{abi}-{platform}.whl;
    # neither the escaped distribution name nor the version contains "-".
    local wheel_file="${url##*/}" wheel_version wheel_uri
    wheel_version="${wheel_file#*-}"
    wheel_version="${wheel_version%%-*}"
    [[ "$wheel_version" == "$version" ]] || {
      printf 'Refusing to install %s %s: its pinned wheel %s is version %s.\n' \
        "$id" "$version" "$wheel_file" "$wheel_version" >&2
      exit 1
    }
    fetch "$url" "$sha256" "$cache_dir/$wheel_file"
    # PEP 508 reads a URI after "@", so the wheel is named by a file:// URL
    # with each path segment percent-encoded (jq's @uri). As a bare path, a
    # "#" in ECO_INSTALL_ROOT would start a fragment and a " ;" a marker, and
    # uv would refuse the install.
    wheel_uri="file://$(jq -rn --arg path "$cache_dir/$wheel_file" '$path | split("/") | map(@uri) | join("/")')"
    spec="${package} @ ${wheel_uri}"
  fi
  UV_TOOL_DIR="$ecosystem_root/python-tools" UV_TOOL_BIN_DIR="$bin_dir" \
    uv tool install --python 3.13 "$spec"
}

# Installs a uv tool pinned to an exact upstream git commit instead of a
# released version (serena: upstream ships no PyPI release of its current
# 2.0.0.dev0). The 40-hex commit is itself the integrity anchor -- git
# refuses to resolve a rev that is not that exact object -- so there is no
# downloaded archive to sha256; install_pin's own fail-closed gate checks
# the commit's shape for this kind instead of a sha256. After install this
# also reads back UV_TOOL_DIR's own uv-receipt.toml and refuses (exit 1)
# unless uv actually resolved that same commit, so a stale prior install of
# a different revision under the same tool name can never pass silently.
install_uv_tool_from_git() {
  # $5 is always given: install_pin below passes the pin's "package" field,
  # falling back to its own "id" in the jq expression itself.
  local id="$1" version="$2" repo_url="$3" commit="$4" package="$5"
  command -v uv >/dev/null || { printf 'uv is required to install %s; install uv first.\n' "$id" >&2; exit 1; }
  UV_TOOL_DIR="$ecosystem_root/python-tools" UV_TOOL_BIN_DIR="$bin_dir" \
    uv tool install --python 3.13 "git+${repo_url}@${commit}"
  local receipt="$ecosystem_root/python-tools/$package/uv-receipt.toml"
  [[ -f "$receipt" ]] || {
    printf 'Refusing %s %s: no uv-receipt.toml at %s after install; cannot verify the resolved commit.\n' \
      "$id" "$version" "$receipt" >&2
    exit 1
  }
  grep -Fq "rev=${commit}" "$receipt" || {
    printf 'Refusing %s %s: %s does not record the pinned commit %s.\n' "$id" "$version" "$receipt" "$commit" >&2
    exit 1
  }
}

# rtk 0.50.0's Claude hook windows `git show <rev>:<path>` blobs (a piped
# `| tail` then reads the window, not the file's end), and a rewritten `diff`
# exits 1 instead of 2 on a missing file. The bare "^git show [^ ]*:" pattern
# misses a `git -C <dir> show HEAD:path` form (still windowed), and separately
# `git branch -a`'s filter_branch_output always keeps git's `+ ` prefix on a
# local branch checked out in a linked worktree, but only misreports it as
# remote-only when a remote-tracking branch of the same name also exists.
# The two added patterns anchor to the git subcommand position (only
# -C/-c/--git-dir/--work-tree with a value, or another --flag, may precede
# show/branch -- the same global options rtk's own discovery strips before
# dispatch), so an ordinary command that merely mentions "show" or "branch"
# as an argument is not misclassified.
# recipes/README.md#native-context-mode-and-hooks excludes all four, and plain
# jq (F2 in docs/decisions/2026-09-26-token-practice-f1-f9.md), through
# rtk's own config (evidence/artifacts/rtk-exclude-widen-20260926/hook-check.txt).
# A duplicate key or table is invalid TOML and rtk silently falls back to
# defaults, so the reminder says to replace the whole value inside the existing
# [hooks] table, adding the key or table only when missing.
# The text check alone is not enough (2026-09-26, Codex review of #314): rtk
# also ignores a TOML-valid file that does not deserialize, for example a
# [tracking] table without history_days (TrackingConfig, src/core/config.rs
# at 1d87b8e7), and then rewrites everything. So once the text matches, the
# installed rtk must answer `rtk hook check` with exactly "No rewrite for:
# <probe>" and exit 1 for every probe, under the caller's own environment
# (XDG_CONFIG_HOME included); any other answer keeps the reminder.
# Print-only: never writes that file (`rtk hook check` writes nothing either).
rtk_config_reminder() {
  local config="${XDG_CONFIG_HOME:-$HOME/.config}/rtk/config.toml"
  local hint="" probe out status
  if [[ -f "$config" ]] \
    && [[ $(grep -Ec '^[[:space:]]*exclude_commands[[:space:]]*=' "$config") -eq 1 ]] \
    && grep -Fq '"^git show [^ ]*:"' "$config" && grep -Fq '"diff"' "$config" && grep -Fq '"jq"' "$config" \
    && grep -Fq "'^git\s+(?:(?:-C|-c|--git-dir|--work-tree)\s+\S+\s+|--\S+\s+)*show\s+(?:[^\n]*\s)?[^\s]*:'" "$config" \
    && grep -Fq "'^git\s+(?:(?:-C|-c|--git-dir|--work-tree)\s+\S+\s+|--\S+\s+)*branch(?:\s|\$)'" "$config"; then
    for probe in 'git show HEAD:x | tail -n 5' 'git -C . show --no-color HEAD:x | tail -n 5' 'diff a missing' \
      'git branch -a' 'git -C . branch' 'jq -r .x f.json'; do
      status=0
      out="$(timeout 30 "$bin_dir/rtk" hook check "$probe" </dev/null 2>&1)" || status=$?
      if [[ "$status" -ne 1 || "$out" != "No rewrite for: $probe" ]]; then
        hint=" The file holds that line, but the installed rtk hook check still rewrites or fails on: $probe; rtk ignores a config it cannot load (for example a [tracking] table without history_days)."
        break
      fi
    done
    [[ -n "$hint" ]] || return 0
  fi
  printf 'Reminder: for the Claude hook, in %s, inside the existing [hooks] table replace the whole exclude_commands value (from "exclude_commands =" through its closing "]"), or add the key if the table lacks it. Add the [hooks] header line only when the file has no [hooks] table. Use: exclude_commands = ["^git show [^ ]*:", "diff", '"'"'^git\s+(?:(?:-C|-c|--git-dir|--work-tree)\s+\S+\s+|--\S+\s+)*show\s+(?:[^\\n]*\s)?[^\s]*:'"'"', '"'"'^git\s+(?:(?:-C|-c|--git-dir|--work-tree)\s+\S+\s+|--\S+\s+)*branch(?:\s|$)'"'"', "jq"] (a duplicate key or table is invalid TOML and rtk silently loads defaults; recipes/README.md#native-context-mode-and-hooks); this script does not write it.%s\n' "$config" "$hint"
}

install_pin() {
  local id="$1"
  local entry
  entry="$(jq -c --arg id "$id" '.tools[] | select(.id == $id)' "$pins_path")"
  if [[ -z "$entry" ]]; then
    printf 'No pin for component %s in %s; skipping.\n' "$id" "$pins_path" >&2
    return 0
  fi
  local version kind url sha256 note commit ignore_scripts
  version="$(jq -r '.version' <<<"$entry")"
  kind="$(jq -r '.kind' <<<"$entry")"
  url="$(jq -r '.url' <<<"$entry")"
  sha256="$(jq -r '.sha256' <<<"$entry")"
  note="$(jq -r '.install_note' <<<"$entry")"
  ignore_scripts="$(jq -r '.ignore_scripts // false' <<<"$entry")"
  if [[ "$kind" == "uv-tool-from-git" ]]; then
    commit="$(jq -r '.commit' <<<"$entry")"
    [[ "$commit" =~ ^[0-9a-f]{40}$ ]] || {
      printf 'Refusing to install %s %s: pin has no verified 40-hex commit (%s)\n' "$id" "$version" "$note" >&2
      exit 1
    }
  elif [[ "$sha256" == "null" || -z "$sha256" ]]; then
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
    *-npm) install_npm "$id" "$version" "$url" "$sha256" "$ignore_scripts" ;;
    *-native) install_native "$id" "$version" "$url" "$sha256" "$(jq -r '.bin // .id' <<<"$entry")" ;;
    *-pip) install_pip "$id" "$version" ;;
    *-uv-tool) install_uv_tool "$id" "$version" "$(jq -r '.package // .id' <<<"$entry")" "$url" "$sha256" ;;
    *-uv-tool-from-git) install_uv_tool_from_git "$id" "$version" "$url" "$commit" "$(jq -r '.package // .id' <<<"$entry")" ;;
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
  'Validate the actual sandbox with Codex /permissions and Claude /sandbox before unattended work.'
if [[ "$configure_full_profile" == 1 ]]; then
  printf '%s\n' 'No model request, project migration or account sign-in was performed; --configure-full-profile follows.'
else
  printf '%s\n' 'No model request, project migration, shell-profile change, or account sign-in was performed.'
fi

# --configure-full-profile, one step at a time. Each step runs the repository's
# own tool for that layer (adoption/bootstrap.md, step 2); each is idempotent,
# so a failed step is reported and the rest still run, and the script exits 6.
full_profile_failed=()
full_profile_rendered=""
full_profile_run() {
  local step="$1" status=0
  shift
  if ! full_profile_selected "$step"; then
    printf '\n-- %s: skipped (--skip %s)\n' "$step" "$step"
    return 0
  fi
  printf '\n-- %s --\n' "$step"
  "$@" || status=$?
  if [[ "$status" -ne 0 ]]; then
    printf -- '-- %s: FAILED (exit %s)\n' "$step" "$status" >&2
    full_profile_failed+=("$step")
  fi
  return 0
}

# render_config.py --out for this host, once, into the run's staging directory;
# the settings and Codex steps read it.
full_profile_render() {
  [[ -z "$full_profile_rendered" ]] || return 0
  python3 "$repo_root/tools/adoption/render_config.py" --host "$full_profile_host" --out "$stage_dir/rendered" || return
  full_profile_rendered="$stage_dir/rendered"
}

# The Claude settings template for this host, then the WSL overlay on WSL, with
# the repository's merge (it backs the file up before writing).
full_profile_claude_settings() {
  full_profile_render || return
  python3 "$repo_root/tools/adoption/apply_claude_settings.py" --template "$full_profile_rendered/settings.json" || return
  if [[ -n "${WSL_DISTRO_NAME:-}" ]]; then
    python3 "$repo_root/tools/adoption/apply_claude_settings.py" \
      --template "$repo_root/adoption/templates/claude.settings.linux-wsl2.overlay.json" || return
  fi
}

# The Codex worker lane goes through apply_codex_lane.py's own reviewed flow,
# whose preconditions a fresh Codex home does not meet: a config.toml with
# features.daemon_auto_start = false, and a HOST_PATH. codex_home.py first
# gives a home without config.toml the rendered user config minus the source
# host's trust state (create-only), and sets the feature in an existing one
# through Codex's own writer; HOST_PATH is the host value file's. The dry run
# then prints the --apply command carrying the two --expect-*-sha256 hashes of
# the files it checked; that command, with the same --codex, --eco-root and
# --host-path, is what runs. The installed codex (an npm package run by node)
# comes from $bin_dir, which need not be on the caller's PATH yet. A failed
# dry run applies nothing.
full_profile_codex_lane() {
  local plan apply_line host_path status=0
  full_profile_render || return
  host_path="$(jq -r '.HOST_PATH // empty' "$repo_root/adoption/hosts/$full_profile_host.json")" || return
  [[ -n "$host_path" ]] || { printf 'adoption/hosts/%s.json has no HOST_PATH.\n' "$full_profile_host" >&2; return 1; }
  PATH="$bin_dir:$PATH" python3 "$repo_root/tools/adoption/codex_home.py" \
    --rendered "$full_profile_rendered/codex.config.toml" --eco-root "$ecosystem_root" --codex "$bin_dir/codex" || return
  plan="$(PATH="$bin_dir:$PATH" python3 "$repo_root/tools/adoption/apply_codex_lane.py" --codex "$bin_dir/codex" \
    --eco-root "$ecosystem_root" --host-path "$host_path" 2>&1)" || status=$?
  printf '%s\n' "$plan"
  [[ "$status" -eq 0 ]] || { printf 'The Codex lane dry run refused (exit %s); nothing applied.\n' "$status" >&2; return "$status"; }
  apply_line="$(printf '%s\n' "$plan" | sed -n 's/^  python3 [^ ]*apply_codex_lane\.py --apply //p' | head -n 1)"
  [[ "$apply_line" =~ --expect-config-sha256\ ([0-9a-f]{64})\ --expect-agents-sha256\ ([0-9a-f]{64}|absent)$ ]] || {
    printf 'The Codex lane dry run printed no --apply command with both hashes; nothing applied.\n' >&2
    return 1
  }
  PATH="$bin_dir:$PATH" python3 "$repo_root/tools/adoption/apply_codex_lane.py" --apply --codex "$bin_dir/codex" \
    --eco-root "$ecosystem_root" --host-path "$host_path" \
    --expect-config-sha256 "${BASH_REMATCH[1]}" --expect-agents-sha256 "${BASH_REMATCH[2]}"
}

# The pinned skills CLI (adoption/skills/manifest.json "cli": its npm tarball and
# sha256), installed with this script's own checksum-verified install_npm when
# it is missing, then the manifest's skills through install_skills.py. The
# install runs in a subshell, so a checksum refusal fails this step only.
full_profile_skills() {
  local manifest="$repo_root/adoption/skills/manifest.json" version tarball sha256 skills_bin
  version="$(jq -r '.cli.version' "$manifest")" || return
  tarball="$(jq -r '.cli.tarball' "$manifest")" || return
  sha256="$(jq -r '.cli.sha256' "$manifest")" || return
  skills_bin="$ecosystem_root/tools/skills-$version/bin/skills"
  if [[ ! -x "$skills_bin" ]]; then
    [[ "$sha256" =~ ^[0-9a-f]{64}$ && "$tarball" == https://registry.npmjs.org/* ]] || {
      printf 'adoption/skills/manifest.json pins no npm tarball and sha256 for the skills CLI; nothing installed.\n' >&2
      return 1
    }
    ( install_npm skills "$version" "$tarball" "$sha256" true ) || return
  fi
  python3 "$repo_root/tools/adoption/install_skills.py" --skills-bin "$skills_bin"
}

# The last step reads the result back: the static login-shell file check and
# where `command -v claude` resolves in a login shell (adoption_status.py
# --launcher-resolution runs that shell, never claude), under the manifest's
# Python as adoption/bootstrap.md step 6 runs it. A claude that is not the
# ecosystem launcher fails the step.
full_profile_login_shell() {
  local report status=0
  report="$(ECO_INSTALL_ROOT="$ecosystem_root" "$bin_dir/uv" run --no-project --python 3.13 python \
    "$repo_root/scripts/adoption_status.py" --profile "$profile_id" --login-shell --launcher-resolution --json)" || status=$?
  printf '%s\n' "$report" | jq '{status, login_shell, launcher_resolution}' || return
  if ! jq -e '.launcher_resolution.is_ecosystem_launcher == true' <<<"$report" >/dev/null; then
    printf 'In a login shell, claude is not the ecosystem launcher %s. If login_shell.profile_read is not true, an earlier ~/.bash_profile or ~/.bash_login hides ~/.profile (adoption/platforms/linux-wsl2.md, "Windows Terminal profiles and the login shell").\n' \
      "$bin_dir/claude" >&2
    return 1
  fi
  return "$status"
}

if [[ "$configure_full_profile" == 1 ]]; then
  command -v python3 >/dev/null || { printf 'python3 is required for --configure-full-profile.\n' >&2; exit 1; }
  printf '\nConfiguring the full user profile (steps: %s)...\n' "${full_profile_steps[*]}"
  full_profile_run claude-profile \
    python3 "$repo_root/tools/adoption/install_claude_profile.py" --claude-bin "$bin_dir/claude" --eco-root "$ecosystem_root"
  full_profile_run claude-settings full_profile_claude_settings
  full_profile_run claude-md python3 "$repo_root/tools/adoption/managed_block.py" claude-md
  full_profile_run skills full_profile_skills
  full_profile_run codex-lane full_profile_codex_lane
  full_profile_run path-block python3 "$repo_root/tools/adoption/managed_block.py" profile-path --eco-root "$ecosystem_root"
  full_profile_run login-shell full_profile_login_shell
  if [[ ${#full_profile_failed[@]} -gt 0 ]]; then
    printf '\n--configure-full-profile: failed step(s): %s. Each step is idempotent: fix the cause, then re-run (--skip the steps already done).\n' \
      "${full_profile_failed[*]}" >&2
    exit 6
  fi
  printf '\n--configure-full-profile: every selected step finished. Open a new login shell so ~/.profile takes effect.\n'
elif [[ "$configure_claude_user_profile" == 1 ]]; then
  command -v python3 >/dev/null || { printf 'python3 is required for --configure-claude-user-profile.\n' >&2; exit 1; }
  printf '\nConfiguring the Claude Code user-scope profile (guard hook, agents, MCP servers)...\n'
  python3 "$repo_root/tools/adoption/install_claude_profile.py" --claude-bin "$bin_dir/claude" --eco-root "$ecosystem_root"
else
  printf '\nAfter native Claude sign-in, run:\n'
  printf '  python3 %q/tools/adoption/install_claude_profile.py --eco-root %q --claude-bin %q\n' "$repo_root" "$ecosystem_root" "$bin_dir/claude"
  printf 'to install the guard hook, agents and user-scope MCP servers (or re-run this script with --configure-claude-user-profile, or --configure-full-profile for the whole user profile).\n'
fi
