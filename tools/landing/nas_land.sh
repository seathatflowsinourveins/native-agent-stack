#!/usr/bin/env bash
# CC landing for native-agent-stack (correction #118): the merge runs only after every gate passes, in this order.
# usage: nas_land.sh <pr> <read-head-sha-prefix> <verdict-file> [<verdict-file> ...]
# Gates: the head equals the read head; every verdict file exists, names that head (prefix) and says PASS or ACK;
# CI has no pending or failing check; mergeStateStatus is not BLOCKED by open threads. Then a squash merge pinned to the head.
# Exit codes: 2 verdict gate, 3 head moved, 5 CI failing, 6 timeout, 7 merge failed, 8 blocked by policy,
# 9 Codex review running, not finished since its latest trigger, or ended other than Completed (codex_gate.py),
# 10 the merge onto CURRENT origin/main fails scripts/validate.py or does not merge cleanly (2026-10-10).
# Correction #136 (2026-10-10): verdict/record acceptance and change identity use the lg_* functions below (land-patches-20261010).
set -u
# Parsed whole before it runs: an edit while a landing runs cannot shift what the running copy executes (2026-10-09).
{
R=seathatflowsinourveins/native-agent-stack
N=${1:?pr}; E=${2:?read head}; shift 2
[ $# -ge 1 ] || { echo "#$N no verdict file given: stop"; exit 2; }
# 2026-10-10: same-change tolerance (as uet_land.sh). A head that is a pure rebase or merge-update of the read head
# (per-file changed lines identical, manifests/evidence.json excluded; CI arbitrates the registry) keeps the reads, and
# a BEHIND branch is updated server-side (gh pr update-branch, merge method) instead of waiting for a lane push.
G="git -C ${LANDING_NAS_REPO:-$HOME/code/native-agent-stack}"; COORD=${LANDING_COORD:-${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack/coordination}
$G fetch -q origin main "pull/$N/head" 2>/dev/null
EF=$($G rev-parse --verify -q "$E^{commit}" 2>/dev/null) || { $G fetch -q origin "$E" 2>/dev/null; EF=$($G rev-parse --verify -q "$E^{commit}"); }
[ -n "$EF" ] || { echo "#$N read head $E not resolvable: stop"; exit 3; }
LG_GIT=$G; LG_EXCLUDE=':!manifests/evidence.json'
# >>> land-gate-fns
# Correction #136 (2026-10-10), tested by trading-cc/land-patches-20261010/harness/run.py. Three decision points were loose or blind:
# (1) a verdict file or record was accepted on "the head prefix anywhere AND PASS/ACK anywhere", which accepts a CHANGES_REQUESTED
#     verdict that mentions ACK elsewhere (19 of 39 real Astra CHANGES_REQUESTED files) and a record whose PASS belongs to another head;
# (2) change() hashed only the +/- lines of each file: it was blind to binary bytes, a mode change, a file name with a space or a
#     non-ASCII character, a removed line starting "--" and an added line starting "++" (git patch-id sees all of them);
# (3) the CI wait counted a commit status (trading-cc-read) as never completed (a commit status has .state, not .status).
lg_hex8() { [[ "$1" =~ ^[0-9a-f]{8}$ ]]; }
# The verdict word of the LAST line that gives a verdict for the head, or nothing. A line gives one in these layouts only:
#   "Gate line: PASS at <head>..."  /  "Verdict: ACK (by closure) at <head>..."     (CC and co-op layouts; the word is PASS|ACK|CHANGES_REQUESTED + [A-Z_0-9]*, then at most one parenthetical, then " at <head>")
#   "...Verdict ... <head>...: PASS ..."  (records, kind=records: the head stands before the first colon, the word right after it)
# Anything else (a pointer line, prose that mentions the head, a PASS elsewhere on the line) gives no verdict.
lg_last_verdict() {  # <file> <8-hex head> <files|records>
  local f=$1 h=$2 kind=$3 w r12 r3 line
  w='((PASS|ACK|CHANGES_REQUESTED)[A-Z_0-9]*)'
  r12='^(Gate line|Verdict): '$w'( \([^)]*\))? at '$h
  r3='(^|[^A-Za-z])([Vv]erdict|VERDICT)[^:]*[^0-9a-f]'$h'[^:]*: *[*_` ]*'$w
  if [ "$kind" = records ]; then
    line=$({ grep -E "$r12|$r3" -- "$f" || true; } | tail -n 1)
  else
    line=$({ grep -E "$r12" -- "$f" || true; } | tail -n 1)
  fi
  if [[ "$line" =~ $r12 ]]; then echo "${BASH_REMATCH[2]}"
  elif [ "$kind" = records ] && [[ "$line" =~ $r3 ]]; then echo "${BASH_REMATCH[3]}"
  fi
}
# A verdict file is accepted by (a) its line 1 in the Astra layout "... <head>...: ACK|PASS ..." or (b) its last Gate line/Verdict line naming
# the head with PASS|ACK[A-Z_0-9]*. CHANGES_REQUESTED anywhere on line 1, or as the word of that last line, rejects; a PASS/ACK anywhere
# else in the file counts for nothing. Prints the reason on stdout when it rejects.
lg_verdict_file_ok() {  # <file> <8-hex head prefix>
  local f=$1 h=$2 l1 w re
  lg_hex8 "$h" || { echo "head prefix '$h' is not 8 lower-case hex characters"; return 1; }
  [ -f "$f" ] || { echo "file missing"; return 1; }
  l1=$(head -n 1 -- "$f" | tr -d '\r')
  [[ "$l1" == *CHANGES_REQUESTED* ]] && { echo "line 1 carries CHANGES_REQUESTED"; return 1; }
  w=$(lg_last_verdict "$f" "$h" files)
  [[ "$w" == CHANGES_REQUESTED* ]] && { echo "the last Gate line/Verdict line naming $h is $w"; return 1; }
  re='(^|[^0-9a-f])'$h'[0-9a-f]*[^:]*: *(ACK|PASS)([^A-Za-z0-9_]|$)'
  [[ "$l1" =~ $re ]] && return 0
  [[ "$w" == PASS* || "$w" == ACK* ]] && return 0
  echo "no accepted verdict naming $h: line 1 must read '...$h...: ACK|PASS' or a Gate line/Verdict line must read 'PASS|ACK at $h'"; return 1
}
# A record (append-only, many heads) is accepted for a head when the LAST line that gives a verdict for it carries PASS or ACK (a section that
# changes a verdict should end with "Gate line: <PASS|ACK|CHANGES_REQUESTED> at <head>"). Prints the reason on stdout when it rejects.
lg_record_ok() {  # <record file> <8-hex head prefix>
  local f=$1 h=$2 w
  lg_hex8 "$h" || { echo "head prefix '$h' is not 8 lower-case hex characters"; return 1; }
  [ -f "$f" ] || { echo "record missing"; return 1; }
  w=$(lg_last_verdict "$f" "$h" records)
  [ -n "$w" ] || { echo "no Verdict/Gate line gives a verdict for $h"; return 1; }
  [[ "$w" == PASS* || "$w" == ACK* ]] && return 0
  echo "the last verdict line for $h is $w"; return 1
}
# The identity of a change: git patch-id (verbatim: whitespace counts; hunk positions do not) of the whole diff at -U0 --binary between
# the commit and its own merge base with origin/main, so mode bits, binary bytes and every file name are in it and a rebase that only
# moves context keeps it. LG_GIT is the git command with its repository, LG_EXCLUDE an optional pathspec to leave out. An empty change
# has no identity (rc 1) and is refused; a change that is empty only because everything in it is excluded is identified by its file names.
lg_change_id() {  # <commit>
  local c=$1 b id names
  b=$(${LG_GIT:-git} merge-base "$c" origin/main) || return 1
  id=$(${LG_GIT:-git} -c core.quotePath=false -c diff.noprefix=false -c diff.mnemonicPrefix=false diff --no-color --no-ext-diff --no-textconv --no-renames -U0 --binary "$b" "$c" -- . ${LG_EXCLUDE:+"$LG_EXCLUDE"} | git patch-id --verbatim | cut -d' ' -f1)
  if [ -n "$id" ]; then echo "$id"; return 0; fi
  names=$(${LG_GIT:-git} -c core.quotePath=false diff --no-renames --name-only "$b" "$c")
  [ -n "$names" ] || return 1
  echo "names:$(printf '%s\n' "$names" | sha256sum | cut -c1-40)"
}
lg_same_change() { local a b; a=$(lg_change_id "$1") || return 1; b=$(lg_change_id "$2") || return 1; [ "$a" = "$b" ]; }
# <<< land-gate-fns
# Correction #136: the identity of a change is git patch-id (verbatim, -U0, --binary) of its whole diff against its own merge base, manifests/evidence.json
# excluded (LG_EXCLUDE); an empty change is refused, and a change that is empty only because everything in it is excluded is identified by its file names.
change() { lg_change_id "$1"; }
same_change() { lg_same_change "$1" "$2"; }
cur=$(gh pr view "$N" -R $R --json headRefOid --jq .headRefOid)
$G cat-file -e "$cur" 2>/dev/null || $G fetch -q origin "$cur"
if [ "$cur" != "$EF" ]; then
  same_change "$EF" "$cur" || { echo "#$N head ${cur:0:8} is neither the read head ${EF:0:8} nor the same change: stop"; exit 3; }
  echo "#$N head ${cur:0:8} carries the read head ${EF:0:8} (same change)"
fi
if [ "$(gh pr view "$N" -R $R --json mergeStateStatus --jq .mergeStateStatus)" = BEHIND ]; then
  gh pr update-branch "$N" -R $R >/dev/null 2>&1 || { echo "#$N update-branch refused (conflict?): a native rebase is needed: stop"; exit 4; }
  sleep 8; $G fetch -q origin main "pull/$N/head"
  cur=$(gh pr view "$N" -R $R --json headRefOid --jq .headRefOid); $G cat-file -e "$cur" 2>/dev/null || $G fetch -q origin "$cur"
  same_change "$EF" "$cur" || { echo "#$N CHANGE DIFFERS after update-branch (${cur:0:8}): stop"; exit 4; }
  echo "#$N updated to ${cur:0:8} on main (same change)"
fi
# trading-cc posts a `trading-cc-read` commit status on its read head (from 2026-10-09T22:50Z), described
# "<VERDICT>: trading-cc/reads/<record>.md" (for example "PASS: …"). A failure blocks. A success counts only when that record exists and names
# the head with PASS or ACK, because a status carries no app identity (any holder of the owner token can post one).
tcc_read_gate() {
  local s st d rec why
  s=$(gh api "repos/$R/commits/$1/statuses?per_page=100" --jq '[.[]|select(.context=="trading-cc-read")]|sort_by(.updated_at)|last|select(.!=null)|"\(.state)\t\(.description)"' 2>/dev/null)
  [ -n "$s" ] || return 0
  st=${s%%$'\t'*}; d=${s#*$'\t'}
  [ "$st" = success ] || { echo "#$N trading-cc-read is $st at ${1:0:8} ($d): stop"; exit 2; }
  # Correction #136: the description's verdict word must be PASS or ACK, and the record's LAST Verdict line naming the head must carry
  # PASS or ACK (not just "the head somewhere and a PASS anywhere").
  [[ "$d" =~ ^(PASS|ACK):\ (trading-cc/reads/[A-Za-z0-9._-]+\.md)$ ]] || { echo "#$N trading-cc-read description not in the agreed form (PASS|ACK: trading-cc/reads/<record>.md): stop"; exit 2; }
  rec=$COORD/${BASH_REMATCH[2]}
  why=$(lg_record_ok "$rec" "${1:0:8}") \
    || { echo "#$N trading-cc-read success at ${1:0:8}, but ${BASH_REMATCH[2]} does not name it with a last PASS/ACK Verdict line ($why): stop"; exit 2; }
  echo "#$N trading-cc-read success at ${1:0:8}; record verified"
}
tcc_read_gate "$EF"
for v in "$@"; do
  [ -f "$v" ] || { echo "#$N verdict file missing: $v"; exit 2; }
  # Correction #136: line 1 "...${EF:0:8}...: ACK|PASS" (the Astra layout) or a Gate line/Verdict line "PASS|ACK at ${EF:0:8}"; CHANGES_REQUESTED on either rejects,
  # and a PASS/ACK anywhere else in the file counts for nothing.
  why=$(lg_verdict_file_ok "$v" "${EF:0:8}") || { echo "#$N verdict $v is not an accepted PASS/ACK verdict for ${EF:0:8} ($why): stop"; exit 2; }
  # Correction #121: a record that states a landing gate needs a receipt for it (GATES_DONE=<receipt naming the head>).
  if grep -q -i -E 'landing gate|path to PASS|before landing|landing condition' "$v"; then
    [ -n "${GATES_DONE:-}" ] && [ -f "$GATES_DONE" ] && grep -q -E "${E:0:8}" "$GATES_DONE" \
      || { echo "#$N verdict $v states a landing gate: set GATES_DONE=<receipt naming ${E:0:8}> after running it"; exit 2; }
  fi
done
# Corrections #122 and #123 (GHA audit T9): a Codex review starts when a PR opens, when a draft is marked ready (by
# anyone) and on an "@codex review" comment; uet#40 and uet#47 merged while one was pending or Running. A draft is
# marked ready first, then codex_gate.py must report the latest review finished (exit 0); running or not yet started
# is polled for up to 20 minutes (exit 9 after that, or when a review ends other than Completed). Its findings become
# threads, which BLOCK below. The gate runs again just before the merge.
GATE=${LANDING_GATE:-$(dirname "$(readlink -f -- "$0")")/codex_gate.py}
codex_wait() {
  local j g gr
  for j in $(seq 1 21); do
    g=$(python3 -I "$GATE" "$R" "$N" 2>&1); gr=$?
    { [ $gr = 0 ] || [ $gr = 5 ]; } && { echo "#$N $g"; return 0; }
    [ $gr = 3 ] && [ $j -lt 21 ] && { sleep 60; continue; }
    echo "#$N $g: stop, land after Codex finishes"; exit 9
  done
}
if [ "$(gh pr view "$N" -R $R --json isDraft --jq .isDraft)" = true ]; then
  gh pr ready "$N" -R $R >/dev/null 2>&1 || { echo "#$N could not be marked ready"; exit 7; }
  echo "#$N marked ready at $(date -u +%FT%TZ)"; sleep 20
fi
codex_wait
# 2026-10-10 (co-op's GPT micro on #923): a PR whose CI ran before a newer main can squash-merge a stale
# manifests/evidence.json registration and turn main red (#923 after #937). Just before the merge: a temporary detached
# worktree at the CURRENT origin/main, a no-commit merge of the head, and scripts/validate.py must exit 0 there (the 5f
# landing rule of 10-09). Exit 10 otherwise: a native rebase with re-registration is needed.
merge_validate() {
  local wt rc err
  $G fetch -q origin main "pull/$N/head" || { echo "#$N fetch failed: stop"; return 1; }
  wt=$(mktemp -d /var/tmp/nas-land-$N-XXXXXX) || return 1
  err=$wt.validate.err
  $G worktree add -q --detach "$wt" origin/main >/dev/null 2>&1 || { echo "#$N worktree add failed: stop"; rmdir "$wt" 2>/dev/null; return 1; }
  if ! git -C "$wt" merge -q --no-commit --no-ff "$1" >/dev/null 2>&1; then
    echo "#$N does not merge cleanly onto main $(git -C "$wt" rev-parse --short HEAD): a native rebase is needed: stop"
    git -C "$wt" merge --abort >/dev/null 2>&1; $G worktree remove --force "$wt" >/dev/null 2>&1; return 1
  fi
  (cd "$wt" && python3 -E -s -B scripts/validate.py >"$err" 2>&1); rc=$?
  git -C "$wt" merge --abort >/dev/null 2>&1; $G worktree remove --force "$wt" >/dev/null 2>&1
  if [ "$rc" != 0 ]; then
    echo "#$N validate.py on the merge with current main exited $rc ($(tail -c 300 "$err" | tr '\n' ' ')): stop"; rm -f "$err"; return 1
  fi
  rm -f "$err"; echo "#$N the merge onto current main validates (rc 0)"; return 0
}
for i in $(seq 1 25); do
  # Judge the LATEST check run per name at this head: superseded runs (concurrency-cancelled duplicates) must not
  # count as failures (2026-10-09 #886: 10 CANCELLED plus 1 FAILURE from a superseded run while mergeState was CLEAN).
  hd=$(gh pr view "$N" -R $R --json headRefOid --jq .headRefOid)
  ms=$(gh pr view "$N" -R $R --json mergeStateStatus --jq .mergeStateStatus)
  # 2026-10-10: the aggregate `validate` check must have SUCCEEDED at this head. A DIRTY PR runs only CodeQL and Socket,
  # so "every check green" alone could pass on a handful of early checks (trading-cc on #940).
  c=$(gh api "repos/$R/commits/$hd/check-runs?per_page=100" --jq '[.check_runs[]|{name,status,conclusion,started_at}]|group_by(.name)|map(max_by(.started_at))|[([.[]|select(.status!="completed")]|length), ([.[]|select(.status=="completed" and (.conclusion=="failure" or .conclusion=="cancelled" or .conclusion=="timed_out" or .conclusion=="action_required"))]|length), length, ([.[]|select(.name=="validate" and .conclusion=="success")]|length)]|@tsv')
  set -- "$hd" $c "$ms"
  vok=${5:-0}; ms=${6:-}; set -- "$1" "$2" "$3" "$4" "$ms"
  [ "${1:-}" = "$cur" ] || { echo "#$N head moved to ${1:-?}: stop"; exit 3; }
  if [ "${2:-1}" = 0 ] && [ "${4:-0}" -gt 0 ] && { [ "${vok:-0}" -gt 0 ] || [ "${3:-0}" -gt 0 ]; }; then
    [ "$3" = 0 ] || { echo "#$N CI failing=$3 of $4: stop"; exit 5; }
    [ "${5:-}" = BLOCKED ] && { echo "#$N BLOCKED by policy with CI green (open threads or required review): stop"; exit 8; }
    g=$(python3 -I "$GATE" "$R" "$N" 2>&1); gr=$?; { [ $gr = 0 ] || [ $gr = 5 ]; } || { echo "#$N $g just before the merge: stop"; exit 9; }
    merge_validate "$cur" || exit 10
    out=$(gh pr merge "$N" -R $R --squash --match-head-commit "$cur" 2>&1) || { echo "#$N merge failed: $out"; exit 7; }
    sleep 4
    echo "#$N $(gh pr view "$N" -R $R --json state,mergeCommit,mergedAt --jq '"\(.state) \(.mergeCommit.oid) \(.mergedAt)"') (CI $4 ok)"
    exit 0
  fi
  sleep 120
done
echo "#$N CI timeout"; exit 6
exit
}
