#!/usr/bin/env bash
# Where rtk 0.50.0 reads its config.toml on macOS, read from upstream source, plus the pinned
# Linux release binary's own read-back (`rtk config`, `rtk hook check`) against scratch configs.
#
# Usage, from the repository root:
#   bash evidence/artifacts/macos-token-pins-20260926/rtk_config_path_check.sh <empty scratch directory>
# Needs git, curl, tar, sha256sum, python3 and read-only network access (github.com, static.crates.io).
#
# local_integration: a harness written for this change, not an upstream test. It prints upstream
# source at the v0.50.0 tag commit and the dirs crate that commit's Cargo.lock pins, then runs the
# upstream linux-x86_64 release binary (verified against adoption/pins-linux-x86_64.json's sha256)
# with HOME set to a scratch directory. No Mac ran it: on macOS only dirs::config_dir() differs,
# and the macOS answer below rests on the printed source and rtk's own documentation.
set -euo pipefail

[[ $# -eq 1 && -d "$1" ]] || { printf 'usage: %s <empty scratch directory>\n' "$0" >&2; exit 2; }
scratch="$(cd "$1" && pwd)"
repo="$(pwd)"
[[ -f "$repo/recipes/README.md" && -f "$repo/adoption/pins-linux-x86_64.json" ]] || {
  printf 'run from the repository root\n' >&2
  exit 2
}
tag_commit=1d87b8e719ce0a50c223cd93ca64dd16921f9aec
upstream=https://github.com/rtk-ai/rtk.git

# Every printed line has the scratch directory replaced by <scratch>; nothing else is changed.
sanitize() {
  local line
  while IFS= read -r line || [[ -n "$line" ]]; do
    printf '%s\n' "${line//"$scratch"/<scratch>}"
  done
}
section() { printf '\n## %s\n' "$1"; }
# Prints the command, its combined output and its exit status.
run() {
  local status=0 output
  printf '$ %s\n' "$*" | sanitize
  output="$("$@" 2>&1)" || status=$?
  [[ -z "$output" ]] || printf '%s\n' "$output" | sanitize
  printf '[exit %s]\n' "$status"
}
numbered() {  # numbered <file> <first> <last>
  awk -v first="$2" -v last="$3" 'NR >= first && NR <= last { printf "%d: %s\n", NR, $0 }' "$1"
}

printf '# rtk 0.50.0 config path on macOS: source read and pinned-binary read-back, %s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '# scratch directory shown as <scratch>; the network was used read-only and nothing was installed.\n'

section "the v0.50.0 tag"
run git ls-remote "$upstream" refs/tags/v0.50.0
src="$scratch/rtk-src"
git init --quiet "$src"
git -C "$src" fetch --quiet --depth 1 "$upstream" "$tag_commit"
git -C "$src" checkout --quiet FETCH_HEAD
run git -C "$src" log -1 --format='%H %s'

section "src/core/config.rs at the tag: get_config_path() and show_config()"
numbered "$src/src/core/config.rs" 495 503
section "src/core/config.rs at the tag: Config::load() reads only that path"
numbered "$src/src/core/config.rs" 315 324
section "environment variables rtk reads by literal name (none selects its config path)"
grep -rhoE 'env::var(_os)?\("[A-Z_]+"\)' "$src/src" | sed -E 's/.*\("([A-Z_]+)"\)/\1/' | sort -u | tr '\n' ' '
printf '\n'
section "environment reads through a named constant"
grep -rnE 'env::var(_os)?\([A-Z_]+\)' "$src/src" | sed "s|$src/||" | sanitize

section "Cargo.lock at the tag: the dirs crates"
grep -n -A3 -E '^name = "dirs(-sys)?"$' "$src/Cargo.lock"

for crate in dirs:5.0.1 dirs-sys:0.4.1; do
  name="${crate%%:*}" version="${crate##*:}"
  curl -sSfL -o "$scratch/$name-$version.crate" "https://static.crates.io/crates/$name/$name-$version.crate"
  locked="$(grep -A3 -E "^name = \"$name\"\$" "$src/Cargo.lock" | sed -n 's/^checksum = "\(.*\)"$/\1/p')"
  actual="$(sha256sum "$scratch/$name-$version.crate" | cut -d' ' -f1)"
  printf '%s-%s.crate sha256 %s; Cargo.lock checksum %s: %s\n' "$name" "$version" "$actual" "$locked" \
    "$([[ "$actual" == "$locked" ]] && echo MATCH || echo MISMATCH)"
  tar -xzf "$scratch/$name-$version.crate" -C "$scratch"
done
section "dirs 5.0.1 src/lib.rs: which module serves macOS"
numbered "$scratch/dirs-5.0.1/src/lib.rs" 23 26
section "dirs 5.0.1 src/mac.rs: config_dir() on macOS"
numbered "$scratch/dirs-5.0.1/src/mac.rs" 5 10
printf 'lines of src/mac.rs naming XDG_CONFIG_HOME: %s\n' "$(grep -c XDG_CONFIG_HOME "$scratch/dirs-5.0.1/src/mac.rs" || true)"
section "dirs 5.0.1 src/lin.rs: config_dir() on Linux, for contrast"
numbered "$scratch/dirs-5.0.1/src/lin.rs" 9 9
section "dirs-sys 0.4.1 src/lib.rs: is_absolute_path(), which lin.rs applies to XDG_CONFIG_HOME"
numbered "$scratch/dirs-sys-0.4.1/src/lib.rs" 8 15
section "dirs-sys 0.4.1 src/lib.rs: home_dir() on unix (a non-empty HOME, else the passwd entry's home)"
numbered "$scratch/dirs-sys-0.4.1/src/lib.rs" 20 21
numbered "$scratch/dirs-sys-0.4.1/src/lib.rs" 33 70
numbered "$scratch/dirs-sys-0.4.1/src/lib.rs" 75 76

section "rtk's own documentation at the tag"
numbered "$src/README.md" 453 453
numbered "$src/docs/guide/getting-started/configuration.md" 12 15

section "the pinned linux-x86_64 binary"
asset=rtk-x86_64-unknown-linux-musl.tar.gz
pinned="$(python3 -c 'import json, sys; print(next(t["sha256"] for t in json.load(open(sys.argv[1]))["tools"] if t["id"] == "rtk"))' \
  "$repo/adoption/pins-linux-x86_64.json")"
curl -sSfL -o "$scratch/$asset" "https://github.com/rtk-ai/rtk/releases/download/v0.50.0/$asset"
printf '%s  %s\n' "$pinned" "$scratch/$asset" | sha256sum --check --strict | sanitize
mkdir -p "$scratch/bin"
tar -xzf "$scratch/$asset" -C "$scratch/bin" rtk
printf 'extracted rtk sha256 %s\n' "$(sha256sum "$scratch/bin/rtk" | cut -d' ' -f1)"

# Not named "home": a committed "/home/<name>/" path reads as a personal path to scripts/validate.py.
home="$scratch/scratch-home"
mkdir -p "$home"
rtk_env() { env -i HOME="$home" PATH=/usr/bin:/bin RTK_TELEMETRY_DISABLED=1 "$@"; }
python3 - "$repo/recipes/README.md" "$scratch/recipe-block.toml" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
block = re.search(r"```toml\n(\[hooks\]\nexclude_commands = \[.*?\n\])\n```", text, re.S).group(1)
open(sys.argv[2], "w", encoding="utf-8").write(block + "\n")
PY
config="$home/.config/rtk/config.toml"
probe='git show HEAD:x | tail -n 5'

printf 'rtk_env below is: env -i HOME=<scratch>/scratch-home PATH=/usr/bin:/bin RTK_TELEMETRY_DISABLED=1\n'
run rtk_env "$scratch/bin/rtk" --version
section "no config file: the first line names the file rtk reads"
run rtk_env "$scratch/bin/rtk" config
section "XDG_CONFIG_HOME moves it on Linux (dirs lin.rs above; mac.rs ignores it)"
run rtk_env XDG_CONFIG_HOME="$scratch/xdg" "$scratch/bin/rtk" config

section "the recipe's block, exactly once"
mkdir -p "${config%/*}"
cp "$scratch/recipe-block.toml" "$config"
run rtk_env "$scratch/bin/rtk" config
run rtk_env "$scratch/bin/rtk" hook check "$probe"

section "the recipe's block twice (a duplicate key): rtk config fails, the hook silently uses defaults"
cat "$scratch/recipe-block.toml" "$scratch/recipe-block.toml" >"$config"
run rtk_env "$scratch/bin/rtk" config
run rtk_env "$scratch/bin/rtk" hook check "$probe"

section "the block once plus a [tracking] table without history_days: valid TOML, still not loadable"
{ printf '[tracking]\nenabled = true\n\n'; cat "$scratch/recipe-block.toml"; } >"$config"
run rtk_env "$scratch/bin/rtk" config
run rtk_env "$scratch/bin/rtk" hook check "$probe"

section "files under the scratch HOME afterwards"
(cd "$home" && find . -type f | LC_ALL=C sort)
