#!/bin/sh
# Self-contained reproduction of the ByteRover CLI offline store/retrieve path.
#
# Usage: sh reproduce-vc-search.sh <output-dir>
#
# Installs the pinned npm release byterover-cli@3.16.1 into a fresh mktemp prefix after
# checking the registry's published integrity against the pinned value, points every
# ByteRover config/data/state directory into the same mktemp workspace (XDG_CONFIG_HOME,
# XDG_DATA_HOME, XDG_STATE_HOME, which src/server/utils/global-*-path.ts honour), commits
# two notes to a project's context tree with `brv vc`, runs `brv search --format json`
# for a positive, a second positive and a negative query, and checks every retained output
# with check_search.py, including two deliberately wrong expectations that must fail.
# `brv restart` then stops the daemon it spawned and the workspace is removed. No LLM,
# network model endpoint, cloud account or host ByteRover state is used. Only <output-dir>
# receives files. The shell/Python checks are local integration glue; the brv outputs are
# the tool's own.
set -u

here=$(cd "$(dirname "$0")" && pwd)
out=${1:?usage: sh reproduce-vc-search.sh <output-dir>}
mkdir -p "$out"
out=$(cd "$out" && pwd)
work=$(mktemp -d)
brv="$work/prefix/bin/brv"
cleanup() {
  [ -x "$brv" ] && (cd "$work/project" 2>/dev/null && "$brv" restart > "$out/90-restart.stdout" 2> "$out/90-restart.stderr")
  rm -rf "$work"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

PIN_VERSION=3.16.1
PIN_INTEGRITY=sha512-uI6zETcy5QO6H29/sdn4BKGWzJl658sjHWxcpO+LHYcmxQj1mAmmi9lluqQZYoXXrnrbp+an8NYhjd5MKmDTcw==

export XDG_CONFIG_HOME="$work/xdg/config" XDG_DATA_HOME="$work/xdg/data" XDG_STATE_HOME="$work/xdg/state"
export DO_NOT_TRACK=1 NO_UPDATE_NOTIFIER=1 npm_config_update_notifier=false BRV_ENV=production MCP_AUTO_OPEN_ENABLED=false

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$out/steps.log"; }
fail() { log "FAIL: $*"; exit 1; }
run() {  # run <label> <command...>: retain stdout/stderr and the exit code
  label=$1; shift
  "$@" > "$out/$label.stdout" 2> "$out/$label.stderr"
  status=$?
  log "$label: exit=$status: $*"
  return $status
}

log "start; workspace is a fresh mktemp directory"
published=$(npm view "byterover-cli@$PIN_VERSION" dist.integrity 2> "$out/00-npm-view.stderr")
printf '%s\n' "$published" > "$out/00-npm-view.stdout"
[ "$published" = "$PIN_INTEGRITY" ] || fail "registry integrity differs from the pinned value"
mkdir -p "$work/pack"
run 01-npm-pack npm pack "byterover-cli@$PIN_VERSION" --pack-destination "$work/pack" || fail "npm pack"
tarball="$work/pack/byterover-cli-$PIN_VERSION.tgz"
python3 -c 'import base64,hashlib,sys; print("sha512-" + base64.b64encode(hashlib.sha512(open(sys.argv[1], "rb").read()).digest()).decode())' \
  "$tarball" > "$out/02-tarball-integrity.stdout" 2> "$out/02-tarball-integrity.stderr" || fail "tarball digest"
[ "$(cat "$out/02-tarball-integrity.stdout")" = "$PIN_INTEGRITY" ] || fail "downloaded tarball differs from the pinned integrity"
run 03-npm-install npm install --global --no-audit --no-fund --prefix "$work/prefix" "$tarball" || fail "npm install"
run 04-version "$brv" --version || fail "brv --version"

mkdir -p "$work/project" && cd "$work/project" || fail "project directory"
run 10-vc-init "$brv" vc init || fail "vc init"
mkdir -p .brv/context-tree/auth .brv/context-tree/billing
printf '%s\n' '# Auth' '' 'Auth uses a fixed-window rate limiter and issues a JWT-like token with a 24 hour (86400s) expiry via issueToken() in src/auth.ts.' > .brv/context-tree/auth/notes.md
printf '%s\n' '# Billing' '' 'Monthly invoices go out on the first business day; each invoice PDF is stored in the billing bucket.' > .brv/context-tree/billing/notes.md
run 11-vc-add "$brv" vc add . || fail "vc add"
run 12-vc-config-name "$brv" vc config user.name "trial-check" || fail "vc config user.name"
run 13-vc-config-email "$brv" vc config user.email "trial-check@example.invalid" || fail "vc config user.email"
run 14-vc-commit "$brv" vc commit -m "Add auth and billing notes" || fail "vc commit"
run 15-vc-log "$brv" vc log || fail "vc log"
run 16-status "$brv" status --format json || fail "status"

run 20-search-positive "$brv" search "rate limiter" --format json
run 21-search-second-positive "$brv" search "invoices" --format json
run 22-search-negative "$brv" search "zzznonexistentxyz123" --format json

checks_ok=0
check() {  # check <label> <expected exit: 0 pass, 1 fail> <checker args...>
  label=$1; want=$2; shift 2
  python3 "$here/check_search.py" "$@" > "$out/$label.stdout" 2> "$out/$label.stderr"
  got=$?
  log "$label: checker exit=$got (intended $want)"
  [ "$got" -eq "$want" ] || checks_ok=1
}
check 30-check-positive 0 "$out/20-search-positive.stdout" --total 1 --path auth/notes.md --text "fixed-window rate limiter"
check 31-check-second-positive 0 "$out/21-search-second-positive.stdout" --total 1 --path billing/notes.md --text "Monthly invoices"
check 32-check-negative 0 "$out/22-search-negative.stdout" --total 0
check 33-check-wrong-path-must-fail 1 "$out/20-search-positive.stdout" --total 1 --path billing/notes.md --text "Monthly invoices"
check 34-check-wrong-count-must-fail 1 "$out/20-search-positive.stdout" --total 10 --path auth/notes.md --text "fixed-window rate limiter"
log "done: every check matched its intended outcome: $([ "$checks_ok" -eq 0 ] && echo yes || echo no)"
exit "$checks_ok"
