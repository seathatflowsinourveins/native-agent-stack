#!/usr/bin/env bash
# Runs tree_drift_check.py on the installed supply-chain-risk-auditor folder and in five controls,
# from the root of a checkout of this repository. Each run's JSON output is written next to this
# script. Stdout gets the checkout HEAD and the check's sha256, one line per run (name, exit,
# extra arguments) and, for the symlink control, the sha256 of the outside uv.lock before and after
# that run. The fixtures are copies of the installed folder in one new directory under $TMPDIR,
# removed on exit.
#
# Usage: TMPDIR=/var/tmp bash evidence/artifacts/skills-listing-restore-20260928/run_checks.sh \
#            > evidence/artifacts/skills-listing-restore-20260928/run_checks.log
set -u
dir=evidence/artifacts/skills-listing-restore-20260928
installed="$HOME/.agents/skills/supply-chain-risk-auditor"
if [ ! -f "$dir/tree_drift_check.py" ] || [ ! -d "$installed" ]; then
  echo "run from the checkout root, on a host with the skill installed" >&2
  exit 2
fi
work=$(mktemp -d "${TMPDIR:-/var/tmp}/tdc-controls.XXXXXX") || exit 2
cleanup() {
  case "$work" in
    "${TMPDIR:-/var/tmp}"/tdc-controls.??????) rm -rf -- "$work" ;;
    *) echo "left in place: $work" >&2 ;;
  esac
}
trap cleanup EXIT
sha256() { python3 -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$1"; }
fixture() { mkdir "$work/$1" && cp -a "$installed" "$work/$1/"; }  # makes $work/<name>/supply-chain-risk-auditor
check() {  # <output name> [extra arguments]
  local name=$1 code
  shift
  python3 "$dir/tree_drift_check.py" --checkout . --skill supply-chain-risk-auditor "$@" > "$dir/$name.json"
  code=$?
  printf '%s exit=%s args=%s\n' "$name" "$code" "$*"
}

printf 'head=%s tree_drift_check.py sha256=%s\n' "$(git rev-parse HEAD)" "$(sha256 "$dir/tree_drift_check.py")"

check tree-drift-check --allow scripts/uv.lock
check control-no-allowance

fixture planted || exit 2
printf '\n' >> "$work/planted/supply-chain-risk-auditor/scripts/model.py"
check control-planted-blob --allow scripts/uv.lock --folder "$work/planted/supply-chain-risk-auditor"

fixture symlink || exit 2
mv "$work/symlink/supply-chain-risk-auditor/scripts" "$work/symlink/outside" || exit 2
ln -s "$work/symlink/outside" "$work/symlink/supply-chain-risk-auditor/scripts" || exit 2
before=$(sha256 "$work/symlink/outside/uv.lock")
check control-symlink --allow scripts/uv.lock --folder "$work/symlink/supply-chain-risk-auditor"
printf 'control-symlink outside/uv.lock sha256 before=%s after=%s\n' "$before" "$(sha256 "$work/symlink/outside/uv.lock")"

fixture special || exit 2
mkfifo "$work/special/supply-chain-risk-auditor/assets/fifo" || exit 2
printf 'gitdir: ../.git/modules/agents\n' > "$work/special/supply-chain-risk-auditor/agents/.git" || exit 2
check control-special-entries --allow scripts/uv.lock --folder "$work/special/supply-chain-risk-auditor"

check control-upstream-gitlink --allow scripts/uv.lock --gh "$dir/fixture_gh_gitlink.py"
