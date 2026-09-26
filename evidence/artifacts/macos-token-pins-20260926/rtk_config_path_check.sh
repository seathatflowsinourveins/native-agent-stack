#!/usr/bin/env bash
# Where rtk 0.50.0 reads its config.toml on macOS, read from upstream source, plus the pinned
# Linux release binary's own read-back (`rtk config`, `rtk hook check`) against scratch configs.
#
# Usage, from the repository root:
#   bash evidence/artifacts/macos-token-pins-20260926/rtk_config_path_check.sh <empty scratch directory>
# Needs git, curl, tar, sha256sum, awk, python3 and read-only network access (github.com, static.crates.io).
#
# local_integration: a harness written for this change, not an upstream test. It prints upstream
# source at the v0.50.0 tag commit and the dirs crates that commit's Cargo.lock pins, then runs the
# upstream linux-x86_64 release binary (verified against adoption/pins-linux-x86_64.json's sha256)
# with HOME set to a scratch directory. No Mac ran it: on macOS only dirs::config_dir() differs,
# and the macOS answer below rests on the printed source and rtk's own documentation.
#
# It fails closed. An integrity check stops the run with exit 1 before anything uses what was
# fetched: the tag must resolve to the pinned commit, the fetched tree must be that commit,
# Cargo.lock must hold exactly one entry for each dirs crate at the expected version, both
# downloaded crates must match their Cargo.lock checksums before either is extracted, and the
# release archive must match its pin. Each binary run is then checked for its exit status and
# output, and the file listing for its contents; the last line is PASS only when every check
# held, and the exit status is 1 when one did not. Every check prints a [check: ...] line.
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
checks=0 failures=0 last_status=0 last_output=

# Every printed line has the scratch directory replaced by <scratch>; nothing else is changed.
sanitize() {
  local line
  while IFS= read -r line || [[ -n "$line" ]]; do
    printf '%s\n' "${line//"$scratch"/<scratch>}"
  done
}
section() { printf '\n## %s\n' "$1"; }
# Prints the command, its combined output and its exit status, and keeps the last two for expect.
run() {
  last_status=0
  printf '$ %s\n' "$*" | sanitize
  last_output="$("$@" 2>&1)" || last_status=$?
  [[ -z "$last_output" ]] || printf '%s\n' "$last_output" | sanitize
  printf '[exit %s]\n' "$last_status"
}
# require <description> <command...>: an integrity check. Unless the command succeeds, it stops
# the run with exit 1, before anything uses what was fetched.
require() {
  local description="$1"
  shift
  checks=$((checks + 1))
  if "$@"; then
    printf '[check: %s: ok]\n' "$description" | sanitize
  else
    printf '[check: %s: FAILED]\nFAIL: an integrity check failed, so the run stops here\n' "$description" | sanitize
    exit 1
  fi
}
# expect <exit status> <is|first-line|has> <text>: checks the last run's exit status and its whole
# output, its first line, or a substring of it. A failed check is counted and the run goes on.
expect() {
  local actual="$last_output" verdict=ok
  [[ "$2" == first-line ]] && actual="${last_output%%$'\n'*}"
  if [[ "$2" == has ]]; then
    [[ "$actual" == *"$3"* ]] || verdict=FAILED
  else
    [[ "$actual" == "$3" ]] || verdict=FAILED
  fi
  [[ "$last_status" == "$1" ]] || verdict=FAILED
  checks=$((checks + 1))
  [[ "$verdict" == ok ]] || failures=$((failures + 1))
  printf '[check: exit %s, output %s "%s": %s]\n' "$1" "$2" "$3" "$verdict" | sanitize
}
numbered() {  # numbered <file> <first> <last>
  awk -v first="$2" -v last="$3" 'NR >= first && NR <= last { printf "%d: %s\n", NR, $0 }' "$1"
}
# lock_entries <name>: "<version> <checksum>" for every [[package]] named <name> in Cargo.lock.
lock_entries() {
  awk -v want="$1" '
    function emit() { if (name == want) print version, checksum; name = version = checksum = "" }
    /^\[\[package\]\]$/ { emit(); next }
    $1 == "name" { name = $3; gsub(/"/, "", name) }
    $1 == "version" { version = $3; gsub(/"/, "", version) }
    $1 == "checksum" { checksum = $3; gsub(/"/, "", checksum) }
    END { emit() }
  ' "$src/Cargo.lock"
}
# one_locked_entry <entries> <version>: exactly one entry, at <version>, with a sha256 checksum.
one_locked_entry() { [[ "$1" =~ ^"$2 "[0-9a-f]{64}$ ]]; }

printf '# rtk 0.50.0 config path on macOS: source read and pinned-binary read-back, %s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '# scratch directory shown as <scratch>; the network was used read-only and nothing was installed.\n'

section "the v0.50.0 tag"
run git ls-remote "$upstream" refs/tags/v0.50.0 'refs/tags/v0.50.0^{}'
# An annotated tag also lists its peeled commit as refs/tags/v0.50.0^{}; a lightweight tag is the commit.
tagged="$(awk '$2 == "refs/tags/v0.50.0^{}" { print $1 }' <<<"$last_output")"
[[ -n "$tagged" ]] || tagged="$(awk '$2 == "refs/tags/v0.50.0" { print $1 }' <<<"$last_output")"
require "tag v0.50.0 resolves to $tag_commit" [ "$last_status:$tagged" = "0:$tag_commit" ]
src="$scratch/rtk-src"
git init --quiet "$src"
git -C "$src" fetch --quiet --depth 1 "$upstream" "$tag_commit"
git -C "$src" checkout --quiet FETCH_HEAD
run git -C "$src" log -1 --format='%H %s'
require "the fetched tree is commit $tag_commit" [ "$(git -C "$src" rev-parse HEAD)" = "$tag_commit" ]

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
# Both crates are downloaded and checked against Cargo.lock before either is extracted.
mismatches=0
for crate in dirs:5.0.1 dirs-sys:0.4.1; do
  name="${crate%%:*}" version="${crate##*:}"
  entries="$(lock_entries "$name")"
  require "Cargo.lock holds exactly one $name entry, $version with a sha256 checksum" \
    one_locked_entry "$entries" "$version"
  locked="${entries#"$version "}"
  curl -sSfL -o "$scratch/$name-$version.crate" "https://static.crates.io/crates/$name/$name-$version.crate"
  actual="$(sha256sum "$scratch/$name-$version.crate" | cut -d' ' -f1)"
  verdict=MATCH
  [[ "$actual" == "$locked" ]] || { verdict=MISMATCH; mismatches=$((mismatches + 1)); }
  printf '%s-%s.crate sha256 %s; Cargo.lock checksum %s: %s\n' "$name" "$version" "$actual" "$locked" "$verdict"
done
require "both crates match their Cargo.lock checksums (neither is extracted otherwise)" [ "$mismatches" -eq 0 ]
for crate in dirs-5.0.1 dirs-sys-0.4.1; do
  tar -xzf "$scratch/$crate.crate" -C "$scratch"
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
printf '%s  %s\n' "$pinned" "$scratch/$asset" >"$scratch/$asset.sha256"
run sha256sum --check --strict "$scratch/$asset.sha256"
require "$asset matches the rtk sha256 in adoption/pins-linux-x86_64.json" [ "$last_status" -eq 0 ]
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
expect 0 is "rtk 0.50.0"
section "no config file: the first line names the file rtk reads"
run rtk_env "$scratch/bin/rtk" config
expect 0 first-line "Config: $config"
section "XDG_CONFIG_HOME moves it on Linux (dirs lin.rs above; mac.rs ignores it)"
run rtk_env XDG_CONFIG_HOME="$scratch/xdg" "$scratch/bin/rtk" config
expect 0 first-line "Config: $scratch/xdg/rtk/config.toml"

section "the recipe's block, exactly once"
mkdir -p "${config%/*}"
cp "$scratch/recipe-block.toml" "$config"
run rtk_env "$scratch/bin/rtk" config
expect 0 first-line "Config: $config"
run rtk_env "$scratch/bin/rtk" hook check "$probe"
expect 1 is "No rewrite for: $probe"

section "the recipe's block twice (a duplicate key): rtk config fails, the hook silently uses defaults"
cat "$scratch/recipe-block.toml" "$scratch/recipe-block.toml" >"$config"
run rtk_env "$scratch/bin/rtk" config
expect 1 has "duplicate key \`hooks\` in document root"
run rtk_env "$scratch/bin/rtk" hook check "$probe"
expect 0 is "rtk $probe"

section "the block once plus a [tracking] table without history_days: valid TOML, still not loadable"
{ printf '[tracking]\nenabled = true\n\n'; cat "$scratch/recipe-block.toml"; } >"$config"
run rtk_env "$scratch/bin/rtk" config
expect 1 has "missing field \`history_days\`"
run rtk_env "$scratch/bin/rtk" hook check "$probe"
expect 0 is "rtk $probe"

section "files under the scratch HOME afterwards"
last_status=0
last_output="$(cd "$home" && find . -type f | LC_ALL=C sort)"
printf '%s\n' "$last_output"
expect 0 is "./.config/rtk/config.toml"

section "result"
if ((failures > 0)); then
  printf 'FAIL: %s of %s checks did not hold\n' "$failures" "$checks"
  exit 1
fi
printf 'PASS: all %s checks held\n' "$checks"
