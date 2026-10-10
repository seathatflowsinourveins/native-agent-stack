#!/usr/bin/env bash
# CC landing for us-equities-trading (private, user-owned, no merge queue; strict up-to-date + linear + squash).
# usage: [VERDICT_FILES="…"] [GATES_DONE=<receipt>] uet_land.sh <pr> <read-head-sha-prefix>
# Steps: verdict checks -> ready -> update-branch --rebase -> the PR's change must equal the read head's change
# (same file set, and per file the same added and removed lines; hunk offsets and context may differ after a rebase)
# -> CI complete with no failure and ci-gate reported -> not BLOCKED by open threads -> squash merge pinned to the head.
# The current head may already be a rebase of the read head (an earlier update-branch); the change check decides.
# Exit codes: 2 verdict gate, 3 head moved, 4 change differs, 5 CI failed, 6 timeout, 7 merge failed, 8 blocked,
# 9 Codex review running, not finished since its latest trigger, or ended other than Completed (codex_gate.py).
# Correction #136 (2026-10-10): verdict/record acceptance, change identity and the CI state use the lg_* functions below (land-patches-20261010).
set -u
# Parsed whole before it runs: an edit while a landing runs cannot shift what the running copy executes (2026-10-09).
{
R=seathatflowsinourveins/us-equities-trading
N=${1:?pr}; E=${2:?read head}
U=${LANDING_UET_REPO:-$HOME/code/us-equities-trading}; COORD=${LANDING_COORD:-${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack/coordination}
git -C $U fetch -q origin main "pull/$N/head"
full=$(git -C $U rev-parse --verify -q "$E^{commit}" 2>/dev/null) || { git -C $U fetch -q origin "$E" 2>/dev/null; full=$(git -C $U rev-parse --verify -q "$E^{commit}"); }
[ -n "$full" ] || { echo "#$N read head $E not resolvable"; exit 3; }
E=$full
LG_GIT="git -C $U"
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
# The CI state of a pull request as one tab-separated line: head, incomplete, failing, total, ci-gate successes, mergeStateStatus.
# A CheckRun is complete when .status is COMPLETED and failing on FAILURE, CANCELLED or TIMED_OUT; a commit status (StatusContext, such as
# trading-cc-read) has .state and no .status: PENDING or EXPECTED is running, FAILURE or ERROR is failing, SUCCESS is complete. A rollup
# entry of any other type counts as running (fail closed). ci-gate is matched on CheckRuns only.
lg_ci_state() {  # <pr>
  gh pr view "$1" -R $R --json headRefOid,statusCheckRollup,mergeStateStatus --jq '[.headRefOid, ([.statusCheckRollup[]|select((.__typename=="CheckRun" and .status!="COMPLETED") or (.__typename=="StatusContext" and (.state=="PENDING" or .state=="EXPECTED")) or (.__typename!="CheckRun" and .__typename!="StatusContext"))]|length), ([.statusCheckRollup[]|select((.__typename=="CheckRun" and .status=="COMPLETED" and (.conclusion=="FAILURE" or .conclusion=="CANCELLED" or .conclusion=="TIMED_OUT")) or (.__typename=="StatusContext" and (.state=="FAILURE" or .state=="ERROR")))]|length), (.statusCheckRollup|length), ([.statusCheckRollup[]|select(.__typename=="CheckRun" and .name=="ci-gate" and .conclusion=="SUCCESS")]|length), .mergeStateStatus]|@tsv' 2>/dev/null
}
# <<< land-gate-fns
# trading-cc posts a `trading-cc-read` commit status on its read head (from 2026-10-09T22:50Z), described
# "<VERDICT>: trading-cc/reads/<record>.md" (for example "PASS: …"). A failure blocks. A success counts only when that record exists and names
# the read head with PASS or ACK, because a status carries no app identity (any holder of the owner token can post one).
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
tcc_read_gate "$E"
# Correction #121: VERDICT_FILES are checked; each names the read head with PASS/ACK, and a stated landing gate needs
# GATES_DONE=<receipt naming the read head>.
for v in ${VERDICT_FILES:-}; do
  [ -f "$v" ] || { echo "#$N verdict file missing: $v"; exit 2; }
  # Correction #136: line 1 "... ${E:0:8}...: ACK|PASS" (the Astra layout) or a Gate line/Verdict line "PASS|ACK at ${E:0:8}"; CHANGES_REQUESTED rejects.
  why=$(lg_verdict_file_ok "$v" "${E:0:8}") || { echo "#$N verdict $v has no PASS/ACK naming ${E:0:8} ($why)"; exit 2; }
  if grep -q -i -E 'landing gate|path to PASS|before landing|landing condition' "$v"; then
    [ -n "${GATES_DONE:-}" ] && [ -f "$GATES_DONE" ] && grep -q -E "${E:0:8}" "$GATES_DONE" \
      || { echo "#$N verdict $v states a landing gate: set GATES_DONE=<receipt naming ${E:0:8}>"; exit 2; }
  fi
done
# Correction #136: the identity of a change is git patch-id (verbatim, -U0, --binary) of its whole diff against its own merge base; an empty change is refused.
change() { lg_change_id "$1"; }
same_change() { lg_same_change "$1" "$2"; }
cur=$(gh pr view "$N" -R $R --json headRefOid --jq .headRefOid)
git -C $U cat-file -e "$cur" 2>/dev/null || git -C $U fetch -q origin "$cur"
if [ "$cur" != "$E" ]; then
  same_change "$E" "$cur" || { echo "#$N head $cur is neither the read head nor a pure rebase of it"; exit 3; }
fi
# Corrections #122 and #123 (GHA audit T9): a Codex review starts when a PR opens, when a draft is marked ready (by
# anyone) and on an "@codex review" comment. #40 merged before its review posted 2 P1 threads, and #47, marked ready by
# another session 23 s before this script ran, merged while its review was Running (4 P2 threads came after). So a
# draft is marked ready first, then codex_gate.py must report the latest review finished (exit 0); running or not yet
# started is polled for up to 20 minutes (exit 9 after that, or when a review ends other than Completed). Findings
# become threads, which BLOCK below. The gate runs again just before the merge.
codex_wait() {
  local j g gr
  for j in $(seq 1 21); do
    g=$(python3 -I "$GATE" "$R" "$N" 2>&1); gr=$?
    { [ $gr = 0 ] || [ $gr = 5 ]; } && { echo "#$N $g"; CODEX_STATE=$gr; return 0; }
    [ $gr = 3 ] && [ $j -lt 21 ] && { sleep 60; continue; }
    echo "#$N $g: stop, land after Codex finishes"; exit 9
  done
}
GATE=${LANDING_GATE:-$(dirname "$(readlink -f -- "$0")")/codex_gate.py}
if [ "$(gh pr view "$N" -R $R --json isDraft --jq .isDraft)" = true ]; then
  gh pr ready "$N" -R $R >/dev/null 2>&1 || { echo "#$N could not be marked ready"; exit 7; }
  echo "#$N marked ready at $(date -u +%FT%TZ)"; sleep 20
fi
codex_wait
# 2026-10-10 (trading-cc proposal, CC ruling): while the Codex connector reports its usage limit, the cross-family pass at
# the head is the co-op's Astra GPT verdict instead. Set GPT_VERDICT=<verdict file naming the read head with ACK/PASS>.
if [ "${CODEX_STATE:-0}" = 5 ]; then
  # Correction #136: the same acceptance as VERDICT_FILES (line 1 "...${E:0:8}...: ACK|PASS", or a Gate line/Verdict line); CHANGES_REQUESTED rejects.
  [ -n "${GPT_VERDICT:-}" ] && why=$(lg_verdict_file_ok "$GPT_VERDICT" "${E:0:8}") \
    || { echo "#$N Codex unavailable: set GPT_VERDICT=<the co-op's Astra verdict naming ${E:0:8} with ACK or PASS on line 1, or a Gate line/Verdict line>${why:+ ($why)}"; exit 9; }
  echo "#$N Codex unavailable; substitute GPT verdict $(basename "$GPT_VERDICT") names ${E:0:8}"
fi
gh pr update-branch "$N" -R $R --rebase >/dev/null 2>&1 || true
sleep 6
git -C $U fetch -q origin main "pull/$N/head"
H=$(gh pr view "$N" -R $R --json headRefOid --jq .headRefOid)
git -C $U cat-file -e "$H" 2>/dev/null || git -C $U fetch -q origin "$H"
same_change "$E" "$H" || { echo "#$N CHANGE DIFFERS between read head ${E:0:8} and head ${H:0:8}: stop"; exit 4; }
echo "#$N read ${E:0:12} -> head ${H:0:12}: same change (file set and per-file changed lines)"
for i in $(seq 1 25); do
  # The required check (ci-gate) must have reported for this head: early-registering checks alone are not "CI done"
  # (2026-10-09 #26: a merge was attempted while only fast checks had registered).
  # Correction #136: lg_ci_state counts a commit status by .state (a PENDING trading-cc-read is running, a SUCCESS one is complete), CheckRuns by .status.
  s=$(lg_ci_state "$N")
  set -- $s
  [ "${1:-}" = "$H" ] || { echo "#$N head moved to ${1:-?} during CI: stop"; exit 3; }
  if [ "${2:-1}" = 0 ] && [ "${4:-0}" -gt 0 ] && { [ "${5:-0}" -gt 0 ] || [ "${3:-0}" -gt 0 ]; }; then
    [ "$3" = 0 ] || { echo "#$N CI failing=$3 of $4: stop"; exit 5; }
    if [ "${6:-}" = BLOCKED ]; then
      open=$(gh api graphql -f query='query($n:Int!){repository(owner:"seathatflowsinourveins",name:"us-equities-trading"){pullRequest(number:$n){reviewThreads(first:100){nodes{isResolved}}}}}' -F n="$N" --jq '[.data.repository.pullRequest.reviewThreads.nodes[]|select(.isResolved==false)]|length')
      echo "#$N BLOCKED by branch policy with CI green; unresolved review threads: $open. Not forcing."; exit 8
    fi
    g=$(python3 -I "$GATE" "$R" "$N" 2>&1); gr=$?; { [ $gr = 0 ] || [ $gr = 5 ]; } || { echo "#$N $g just before the merge: stop"; exit 9; }
    out=$(gh pr merge "$N" -R $R --squash --match-head-commit "$H" 2>&1) || { echo "#$N merge failed: $out"; exit 7; }
    sleep 4
    echo "#$N $(gh pr view "$N" -R $R --json state,mergeCommit,mergedAt --jq '"\(.state) \(.mergeCommit.oid) \(.mergedAt)"') (CI $4 ok)"
    exit 0
  fi
  sleep 120
done
echo "#$N CI timeout"; exit 6
exit
}
