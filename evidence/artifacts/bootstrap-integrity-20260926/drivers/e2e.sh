#!/usr/bin/env bash
# local_integration end-to-end check (self-written driver; not an upstream test and not CI).
# Four scenarios, run serially, each through bootstrap_once.sh:
#   pass            fixed script, the checkout's pins,               profile {headroom, socraticode}
#   fixed-bad-hash  fixed script, headroom sha256 set to 64 zeros,   profile {headroom}
#   head-bad-hash   HEAD's script, the same zeroed pins,             profile {headroom, socraticode}
#   transition      one root: HEAD's script, then the fixed script twice, profile {headroom}
# The first is the claim; the second shows the fixed script's check fails when its condition is
# absent; the third shows the same wrong hash and socraticode's ignore_scripts are not consulted by
# HEAD's script, so the second and first can tell the two scripts apart.
#   usage: e2e.sh CHECKOUT WORK
set -uo pipefail
checkout="$1" work="$2"
here="$(cd "$(dirname "$0")" && pwd -P)"
# WORK must be new, an empty directory, or a directory these drivers created (work_guard.sh).
# shellcheck source-path=SCRIPTDIR source=work_guard.sh
. "$here/work_guard.sh" || exit 2
claim_work "$work" || exit 2
rm -rf "$work"
mkdir -p "$work"
mark_work "$work"
fixed="$checkout/adoption/bootstrap-linux.sh"
head_script="$work/head-bootstrap-linux.sh"
git -C "$checkout" show HEAD:adoption/bootstrap-linux.sh >"$head_script"
printf 'checkout HEAD %s\n' "$(git -C "$checkout" rev-parse HEAD)"
printf 'fixed script  %s (working tree)\n' "$(sha256sum <"$fixed" | cut -d' ' -f1)"
printf 'HEAD script   %s (git show HEAD:adoption/bootstrap-linux.sh)\n' "$(sha256sum <"$head_script" | cut -d' ' -f1)"
pins="$checkout/adoption/pins-linux-x86_64.json"
bad_pins="$work/pins-headroom-bad-hash.json"
jq '.tools |= map(if .id == "headroom" then .sha256 = ("0" * 64) else . end)' "$pins" >"$bad_pins"
uv_cache="$work/uv-cache"
"$here/bootstrap_once.sh" pass "$fixed" "$pins" "$work" "$uv_cache" '["headroom","socraticode"]' "$work/eco-pass"
seed="$work/eco-pass/downloads"
"$here/bootstrap_once.sh" fixed-bad-hash "$fixed" "$bad_pins" "$work" "$uv_cache" '["headroom"]' \
  "$work/eco-fixed-bad-hash" "$seed"
"$here/bootstrap_once.sh" head-bad-hash "$head_script" "$bad_pins" "$work" "$uv_cache" '["headroom","socraticode"]' \
  "$work/eco-head-bad-hash" "$seed"
"$here/bootstrap_once.sh" t1-head "$head_script" "$pins" "$work" "$uv_cache" '["headroom"]' "$work/eco-transition" "$seed"
"$here/bootstrap_once.sh" t2-fixed "$fixed" "$pins" "$work" "$uv_cache" '["headroom"]' "$work/eco-transition"
"$here/bootstrap_once.sh" t3-fixed "$fixed" "$pins" "$work" "$uv_cache" '["headroom"]' "$work/eco-transition"
